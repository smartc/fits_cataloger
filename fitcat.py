# FITS Cataloger Tools
# (c) 2020 Corey Smart
#
# Rev. 0 - 29 Dec 2020
#
# Python tools for processing and cataloging of FITS images on hard drive.
#
#  General Workflow: (** denotes steps done in python, other steps are outside of scope)
#
#					Capture images on remote / observing computer
#					Transfer images to "quarantine" folder on primary machine
#
#					**df = process_subfolders() 			returns dataframe with all images found
#					**writeTemp(df) 						outputs dataframe to temporary SQL database table
#
#					**df = readTemp()						updates dataframe with changes made to temp table
#					**moveFiles(df)							moves accepted files from temp folder to long term library
#
#					Inspect files in updated folder structure, use revertFiles() process if necessary to pull them back to original locations
#					Append temp table to main table in SQL database
#
#  TODO:
#		4) Remove 'index' from initial dataframe
#		5) Incorporate platesolving to initial data collection
#		7) Migrate from SQLite to MySQL or other online database
#		8) Move Telescope and Camera identification criteria to external JSON or database
#		9) Move configuration data (default_dir, library_db) to external JSON



import os, inspect, sys
import pandas as pd
from glob import glob
from astropy.io import fits
from sqlalchemy import create_engine
from hashlib import md5
from datetime import timedelta
#import astrometry as astropy							# not used
from progress.bar import Bar


quarantine_dir = "/path/to/your/quarantine"				# define absolute path to your quarantine folder
image_dir = "/path/to/your/images" 						# define absolute path to folder where you wish to store images
library_db = "/path/to/your/database.db"				# define absolute path to sqlite3 database file that will store data about your images
restore_folder = "/path/to/a/temporary/folder"			# used only if you need to roll back changes (manual process)
fits_table = "fits_files"
temp_table = "fits_temp"
temp_solved = "plate_solve_temp"
temp_errors = "error_log_temp"

# List of cameras
# format is [ ['CAMERA 1', x_pixels, y_pixels ], ['CAMERA 2', x_pixels, y_pixels] ]
CAMERAS = [ ['ASI1600', 4656, 3520], ['ASI183', 5496, 3672], ['EOST4i', 5208, 3476], ['EOSRP', 6264, 4180], ['QSI683', 3326, 2504]]

# List of telescopes / lenses
# format is [ ['SCOPE 1', focal_length], ['SCOPE 2', focal_length] ]
TELESCOPES = [ ['ES127', 952], ['ES127', 666], ['ED80-T', 480], ['ROKINON_135', 135], ['ROKINON_FE14M', 14]]


# return a list of FITS files in the specified subfolder
def list_fits(prefix = "", imageType = "fit*"):
	filePattern = prefix + "*." + imageType
	images = glob(filePattern)
	images.sort()
	return images



# navigate specified folder and all subfolders and return dataFrame object with header info for all FITS files found
def process_subfolders(tgtDir = None, include_duplicates = False, purge_bad = True):
	if tgtDir is None:
		tgtDir = quarantine_dir
	os.chdir(tgtDir)
	data = []
	temp_df = loadLibrary()
	indx = temp_df.reset_index().id.max() + 1
	new_files = 0
	duplicates = 0
	bad_files = []
	for subdir, dirs, files in os.walk(tgtDir):
		os.chdir(subdir)
		print("Switching to folder: " + subdir)
		images = list_fits()
		for f in images:
			if not ('BAD_' in f):
				try:
					row = get_data(f, indx)
					duplicate = temp_df['md5sum'].isin([row['md5sum']]).any().any()
					if not duplicate or include_duplicates:
						data.append(row)
						indx += 1
						new_files += 1
					else:
						duplicates += 1
				except:
					print("Error in file: {}".format(os.path.join(os.getcwd(), f)))
					raise
			else:
					bad_files.append(os.path.join(subdir,f))
	os.chdir(tgtDir)
	df = pd.DataFrame(data)
	print("Found {} new files and {} duplicates.".format(new_files, duplicates))
	print("Found {} bad files.".format(len(bad_files)))
	if purge_bad:
			for f in bad_files:
				print("*** Removing image flagged as bad: {} ***".format(f))
				os.remove(f)
	return df



# get list of FITS key words in specified file header
def list_keys(filename):
	img = fits.open(filename)
	hdr = img[0].header
	keys = list(hdr.keys())
	return keys



# get selected header information from specified file and return dictionary of data found
def get_data(f, index = None):
	d = os.getcwd()
	img = fits.open(f)[0]
	ra = get_keyData(img, 'OBJCTRA')
	dec = get_keyData(img, 'OBJCTDEC')
	dt = get_keyData(img, 'DATE-OBS')
	x_size = get_keyData(img, 'NAXIS1')
	y_size = get_keyData(img, 'NAXIS2')
	ft = get_keyData(img, 'IMAGETYP')
	o = get_keyData(img, 'OBJECT')
	fe = get_keyData(img, 'FILTER', '<none>')
	fe = cleanFilters(fe)
	fl = get_keyData(img, 'FOCALLEN')
	exp = get_keyData(img, 'EXPOSURE')
	binning = get_keyData(img, "XBINNING")
	if binning == None:					# if not defined per above keyword, try this keyword instead
		get_keyData(img,'BINNING')
	if binning == None:
		binning = 1						# if still not defined, assume it's '1'
	cam = idCamera(x_size, binning=binning)
	tel = idTelescope(fl)
	md5 = getHash(f)
	data = { 'id': index, 'file': f, 'folder': d, 'object': o, 'obs-date': dt, \
		   'ra': ra, 'dec': dec, 'x': x_size, 'y': y_size, 'frame_type': ft, \
			'filter': fe, 'focal_length': fl, 'exposure': exp, 'camera': cam,
			'telescope': tel, 'md5sum': md5 }
	return data



# retrieve data from header key and return
def get_keyData(img, key, alt = None):
	if key in list(img.header.keys()):
		return img.header[key]
	else:
		return alt



# identify camera used to take an image based on the number of pixels in the x-axis
def idCamera( x, y = None, binning = 1 ):
	global CAMERAS
	if (binning != 1):
		x = x * binning
		if y is not None:
			y = y* binning
	for i in range(0, len(CAMERAS)):
		if CAMERAS[i][1] == x:
			return CAMERAS[i][0]
	return '<unknown>'


# identify telescope / lens used based on focal length
def idTelescope( fl ):
	if fl is None:
		return None
	global TELESCOPES
	for i in range(0, len(TELESCOPES)):
		if TELESCOPES[i][1] == fl:
			return TELESCOPES[i][0]
	return '<unknown>'

# get md5 signature of specified file
def getHash(f):
	hash = md5(open(f, 'rb').read()).hexdigest()
	return hash



# return subset of all dataFrame entries with duplicates
def allDups():
	global df
	alldups = df[df['duplicate'] == True]
	return alldups



# return subset of dataFrame of other entries with same md5sum
def findDups(i):
	global df
	subset = df[df['md5sum'] == df.loc[i]['md5sum']]
	return subset



# mark entries with duplicate md5sums for deletion
def markDups(i):
	global df
	dups = findDups(i)
	for j in dups.index:
		if j != dups.index.min():
			df.loc[j, 'delete_me'] = True
		else:
			df.loc[j, 'delete_me'] = False



# get night of session for when image was acquired:
def sessionNight(d):
	# offset time by 12 hours to get night on which session started
	d = d - timedelta(hours=12)
	night = d.strftime("%Y-%m")
	return night



# move files in dataset to new location
def moveFiles(mvDF, justUpdate=False):
	root_folder = image_dir
	with Bar("Moving files", max=mvDF.file.count()) as bar:
		for i in mvDF.index:
			obj = mvDF.loc[i, 'object']
			cam = mvDF.loc[i, 'camera']
			tel = mvDF.loc[i, 'telescope']
			if tel is None or tel == '' or tel == "<none>":
				tel = "_none_"
			night = sessionNight(mvDF.loc[i, 'obs-date'])
			frm = mvDF.loc[i, 'frame_type']
			flt = mvDF.loc[i, 'filter']
			if flt == "<none>":
				flt = "_none_"
			idx = str(i).zfill(6)
			fn = mvDF.loc[i, 'file']
			fld = mvDF.loc[i, 'folder']
			if frm == "DARK" or frm == "BIAS" or frm == "DARK_FLAT":
				base_folder = os.path.join(root_folder, obj, cam, frm, flt, night)
				new_file = os.path.join(base_folder, str(idx) + "_" + fn)
			elif frm == "FLAT":
				base_folder = os.path.join(root_folder, obj, cam, frm, tel, flt, night)
				new_file = os.path.join(base_folder, str(idx) + "_" + fn)
			else:
				base_folder = os.path.join(root_folder, obj, cam, tel, flt, night)
				new_file = os.path.join(base_folder, str(idx) + "_" + fn)
			if not justUpdate:
				isdir = os.path.isdir(base_folder)
				if not isdir:
					os.makedirs(base_folder)
				os.rename(os.path.join(fld,fn), new_file)
			mvDF.loc[i, 'orig_folder'] = mvDF.loc[i, 'folder']
			mvDF.loc[i, 'orig_file'] = mvDF.loc[i, 'file']
			mvDF.loc[i, 'folder'] = base_folder
			mvDF.loc[i, 'file'] = str(idx) + "_" + fn
			mvDF.loc[i, 'obs-date'] = mvDF.loc[i, 'obs-date'].strftime("%Y-%m-%dT%H:%M:%S")
			bar.next()
		return mvDF



# load data from library:
def loadLibrary():
	global library_db
	global fits_table
	engine = create_engine("sqlite:///"+library_db, echo=False)
	sql_conn = engine.connect()
	df = pd.read_sql("SELECT * FROM " + fits_table , sql_conn, parse_dates={'obs-date': '%Y-%m-%dT%H:%M:%S'})
	sql_conn.close()
	df = df.set_index('id')
	return df



# write df dataFrame to temp_table:
def writeTemp(df, tbl = temp_table):
	global library_db
	engine = create_engine("sqlite:///"+library_db, echo=False)
	sql_conn = engine.connect()
	df.to_sql(tbl, sql_conn, if_exists='replace')
	sql_conn.close()



# clean up folders:
def cleanFolders():
	df = loadLibrary()
	moveFiles(df)
	writeTemp(df)
	return df



# roll back changes from temp file if necessary:
def revertFiles():
	global library_db
	engine = create_engine("sqlite:///"+library_db, echo=False)
	sql_conn = engine.connect()
	df = pd.read_sql("SELECT * FROM " + temp_table , sql_conn, parse_dates={'obs-date': '%Y-%m-%dT%H:%M:%S'})
	sql_conn.close()
	df = df.set_index('id')
	for i in df.index:
		old_file = os.path.join(df.loc[i, 'folder'], df.loc[i, 'file'])
		base_folder = df.loc[i, "orig_folder"]
		new_file = df.loc[i, "orig_file"]
		isdir = os.path.isdir(base_folder)
		if not isdir:
			os.makedirs(base_folder)
		os.rename(old_file, os.path.join(base_folder,new_file))



# load temporary data from 
def readTemp(readTable = temp_table, idx = 'id'):
	global library_db
	global temp_table
	engine = create_engine("sqlite:///"+library_db, echo=False)
	sql_conn = engine.connect()
	df = pd.read_sql("SELECT * FROM " + readTable , sql_conn, parse_dates={'obs-date': '%Y-%m-%dT%H:%M:%S'})
	sql_conn.close()
	if idx is not None:
		df = df.set_index(idx)
	return df



def loadLightFrames():
	df = loadLibrary()
	df = df[df['frame_type'] == "LIGHT"]
	return df



# plate solve images in folder using self hosted astrometry server
def solveImages():
	data = []
	errors = []
	df = loadLightFrames()
	# ASTAP solver command
	astap_cmd = 'astap -wcs '
	with Bar("Processing", max = df.file.count()) as bar:
		for i in df.index:
			f = df.loc[i,'file']
			d = df.loc[i, 'folder']
			file = os.path.join(d, f)
			cmd = astap_cmd + '-f ' + file + " >/dev/null 2>&1"
			result = os.system(cmd)
			if result == 0:
				try:
					w = file[:-3]+'wcs'
					hdr = fits.open(w)[0].header
					ra = hdr['RA']
					dec = hdr['DEC']
					angle = hdr['ANGLE']
					pixscale = hdr['SCALE']
					r = { 'index': i, 'ra_solved': ra, 'dec_solved': dec, "angle_solved": angle, 'pixscale': pixscale}
					data.append(r)
				except Exception as e:
					errors.append({'index': i,'file': f, 'folder': d, 'error': e})
			bar.next()
	df = pd.DataFrame(data)
	writeTemp(df, temp_solved)
	if errors:
		errs = pd.DataFrame(errors)
		writeTemp(errs, temp_errors)
	return df



# replace corrupted files from backup location to location identified in database
def restoreFiles():
	oldDF = loadLibrary()
	global restore_folder
	newDF = process_subfolders(restore_folder)
	print("Getting MD5 signatures of restored files...")
	with Bar("Processing MD5 signatures", max=newDF.file.count()) as bar:
		for i in newDF.index:
			d = newDF.loc[i, "folder"]
			f = newDF.loc[i, "file"]
			file = os.path.join(d,f)
			md5 = getHash(file)
			newDF.loc[i, "md5sum"] = md5
			bar.next()
	matches = findMatches(oldDF, newDF)
	# do the move



def moveRestored(matches):
	errors = []
	with Bar("Moving Files", max = matches.old_file.count()) as bar:
		for i in matches.index:
			try:
				ofold = matches.loc[i, "old_folder"]
				ofile = matches.loc[i, "old_file"]
				nfold = matches.loc[i, "new_folder"]
				nfile = matches.loc[i, "new_file"]
				f1 = os.path.join(ofold, ofile)
				f2 = os.path.join(nfold, nfile)
				os.remove(f1)
				os.rename(f2, f1)
				matches.loc[i, "restored"] = True
			except Exception as e:
				err = {"index": i, "old": f1, "new": f2, "error": e}
				errors.append(err)
			bar.next()
	if errors:
		return errors
	else:
		return 0



def findMatches(oldDF, newDF):
	matches = []
	with Bar("Finding matches", max = oldDF.file.count()) as bar:
		for i in oldDF.index:
			md5 = oldDF.loc[i, "md5sum"]
			if isinstance(md5, str):	
				mtch = newDF[newDF["md5sum"] == md5]
				if len(mtch):
					old = i
					new = mtch.reset_index().loc[0, "id"]
					matches.append({"old_id": old, "new_id": new})
			bar.next()
	matches = pd.DataFrame(matches)
	return matches


def fixIDs(df):
	with Bar("Finding matches", max = df.file.count()) as bar:
		for i in df.index:
			file_name = df.loc[i, "file"]
			file_number = int(file_name[0:6])
			if file_number != i:
				folder = df.loc[i, "folder"]
				new_name = str(i).zfill(6) + file_name[6:]
				os.rename(os.path.join(folder, file_name), os.path.join(folder, new_name))
				df.loc[i, "file"] = new_name
			bar.next()



def calcHashes():
	df = loadLibrary()
	misdf = df[df['md5sum'].isnull()]
	with Bar("Generating md5sums", max=misdf.file.count()) as bar:
		for i in misdf.index:
			file = misdf.loc[i, "file"]
			fold = misdf.loc[i, "folder"]
			f = os.path.join(fold, file)
			try:
				md5 = getHash(f)
				df.loc[i, "md5sum"] = md5
			except FileNotFoundError:
				df.loc[i, "file_not_found"] = True
			bar.next()
	return df


def cleanFilters(flt):
	filter_data = [ ["Red", "Green", "Blue", "Lum", "Sii", "Oiii"], ["R", "G", "B", "L", "SII", "OIII"] ]
	if flt in filter_data[0]:
		i = filter_data[0].index(flt)
		flt = filter_data[1][i]
	return flt

def appendTemps():
	global library_db
	SQL = "INSERT INTO fits_files (id, file, folder, 'object', 'obs-date', ra, 'dec', x, y, frame_type, camera, focal_length, 'filter', exposure, telescope, md5sum)SELECT ft.id, ft.file, ft.folder, ft.'object', ft.'obs-date', ft.ra, ft.'dec', ft.x, ft.y, ft.frame_type, ft.camera, ft.focal_length, ft.'filter', ft.exposure, ft.telescope, ft.md5sum  FROM fits_temp ft ;"
	from sqlalchemy.sql import text
	statement = text(SQL)
	engine = create_engine("sqlite:///"+library_db, echo=False)
	sql_conn = engine.connect()
	sql_conn.execute(statement)
	sql_conn.close()


def removeEmptyFolders(abs_path = None):
	if abs_path is None:
		abs_path = quarantine_dir
	walk = list(os.walk(abs_path))[1:]
	for path, _, _ in walk[::-1]:
		if len(os.listdir(path)) == 0:
			print("Removing empty folder:    " + path)
			os.rmdir(path)
		else:
			print("Leaving non-empty folder: " + path)

# command line behaviour
if __name__ == "__main__":
	try:
		tgtDir = sys.argv[1]
	except IndexError:
		tgtDir = None
	except:
		print("Unexpected error: {}".format(sys.exc_info()[0]))
		raise
	
	df=process_subfolders(tgtDir)
	if (df.size > 0):
		writeTemp(df)
		df=readTemp()
		df=moveFiles(df)
		writeTemp(df)
		appendTemps()
	removeEmptyFolders()