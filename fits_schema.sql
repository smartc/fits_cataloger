CREATE TABLE fits_files_bak (
	id BIGINT,
	file TEXT,
	folder TEXT,
	"object" TEXT,
	"obs-date" TEXT,
	ra TEXT,
	"dec" TEXT,
	x BIGINT,
	y BIGINT,
	frame_type TEXT,
	"filter" TEXT,
	focal_length FLOAT,
	exposure FLOAT,
	camera TEXT,
	md5sum TEXT,
	duplicate BIGINT,
	instances BIGINT,
	purged BOOLEAN,
	telescope TEXT
);
CREATE VIEW file_location_updates AS 
SELECT ft.id as temp_id, ft.file as new_file, ft.folder as new_folder, ffb.file as old_file, ffb.folder as old_folder FROM fits_temp ft
JOIN fits_files_bak ffb ON ft.id = ffb.id
/* file_location_updates(temp_id,new_file,new_folder,old_file,old_folder) */;
CREATE TABLE process_log (
	id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	session_name TEXT NOT NULL,
	"object" TEXT,
	image_type TEXT,
	create_date INTEGER
, status INTEGER DEFAULT 0, astrobin_path TEXT);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE process_log_files (
	id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	session_id INTEGER NOT NULL,
	image_id INTEGER NOT NULL,
	notes TEXT
);
CREATE VIEW calibration_summary AS
SELECT ff.camera, ff.frame_type, ff.filter, DATE("obs-date") as "date", COUNT(id) as N, SUM(ff.exposure) as "total exposure", ff.folder
FROM fits_files ff 
WHERE ff.object LIKE "_CALIBRATION_" OR ff."object"  LIKE "_MASTERS_"
GROUP BY "camera", frame_type , "filter", "folder", "date"
/* calibration_summary(camera,frame_type,"filter",date,N,"total exposure",folder) */;
CREATE TABLE IF NOT EXISTS "cameras" (
	camera_id INTEGER PRIMARY KEY AUTOINCREMENT,
	camera_name TEXT,
	x_res INTEGER,
	y_res INTEGER,
	pixel_size INTEGER
);
CREATE VIEW image_scales AS
SELECT ff."object", ff.camera, c.x_res, c.y_res, c.pixel_size, 
		ROUND(((c.pixel_size * c.x_res *3.460) / ff.focal_length ), 0) AS x_scale,
		ROUND(((c.pixel_size * c.y_res *3.460) / ff.focal_length ), 0) AS y_scale
FROM fits_files ff 
JOIN cameras c ON ff.camera  = c.camera_name 
WHERE ff.frame_type LIKE "LIGHT"
GROUP BY ff."object", ff.camera
/* image_scales(object,camera,x_res,y_res,pixel_size,x_scale,y_scale) */;
CREATE TABLE plate_solve_temp (
	level_0 BIGINT, 
	"index" BIGINT, 
	ra_solved FLOAT, 
	dec_solved FLOAT, 
	angle_solved FLOAT, 
	pixscale FLOAT
);
CREATE INDEX ix_plate_solve_temp_level_0 ON plate_solve_temp (level_0);
CREATE TABLE matched_temp (
	"index" BIGINT, 
	old_id BIGINT, 
	new_id BIGINT
);
CREATE INDEX ix_matched_temp_index ON matched_temp ("index");
CREATE TABLE restored_fits (
	id BIGINT, 
	file TEXT, 
	folder TEXT, 
	object TEXT, 
	"obs-date" DATETIME, 
	ra TEXT, 
	dec TEXT, 
	x BIGINT, 
	y BIGINT, 
	frame_type TEXT, 
	filter TEXT, 
	focal_length FLOAT, 
	exposure FLOAT, 
	camera TEXT, 
	md5sum TEXT
);
CREATE INDEX ix_restored_fits_id ON restored_fits (id);
CREATE TABLE md5_matches (
	"index" BIGINT, 
	old_id BIGINT, 
	new_id BIGINT, 
	old_folder TEXT, 
	old_file TEXT, 
	new_folder TEXT, 
	new_file TEXT
);
CREATE INDEX ix_md5_matches_index ON md5_matches ("index");
CREATE TABLE error_log (
	level_0 BIGINT, 
	"index" BIGINT, 
	old TEXT, 
	new TEXT, 
	error TEXT
);
CREATE INDEX ix_error_log_level_0 ON error_log (level_0);
CREATE TABLE error_log_temp (
	level_0 BIGINT, 
	"index" BIGINT, 
	old TEXT, 
	new TEXT, 
	error TEXT
);
CREATE INDEX ix_error_log_temp_level_0 ON error_log_temp (level_0);
CREATE TABLE fits_files (
	id BIGINT, 
	file TEXT, 
	folder TEXT, 
	object TEXT, 
	"obs-date" DATETIME, 
	ra TEXT, 
	dec TEXT, 
	x BIGINT, 
	y BIGINT, 
	frame_type TEXT, 
	filter TEXT, 
	focal_length FLOAT, 
	exposure FLOAT, 
	camera TEXT, 
	md5sum TEXT, 
	duplicate FLOAT, 
	instances FLOAT, 
	purged FLOAT, 
	telescope TEXT, 
	orig_file TEXT, 
	orig_folder TEXT, 
	bad TEXT, 
	file_not_found BOOLEAN, 
	CHECK (file_not_found IN (0, 1))
);
CREATE TABLE broken_df (
	id BIGINT, 
	"index" BIGINT, 
	file TEXT, 
	folder TEXT, 
	object TEXT, 
	"obs-date" TEXT, 
	ra TEXT, 
	dec TEXT, 
	x BIGINT, 
	y BIGINT, 
	frame_type TEXT, 
	filter TEXT, 
	focal_length FLOAT, 
	exposure BIGINT, 
	camera TEXT, 
	telescope TEXT, 
	md5sum TEXT, 
	orig_folder TEXT, 
	orig_file TEXT
);
CREATE INDEX ix_broken_df_id ON broken_df (id);
CREATE UNIQUE INDEX fits_files_id_IDX ON fits_files (id);
CREATE VIEW target_summary AS 
SELECT ff.object, ff.camera, ff.filter, DATE("obs-date") as "date", ff.exposure, COUNT(id) as N, (ff.exposure * count(id)) as total_exposure
FROM fits_files ff 
WHERE ff.object NOT LIKE "_CALIBRATION_" AND ff."object" NOT LIKE "_MASTERS_" AND (ff.purged <> "TRUE" OR ff.purged IS NULL) AND (ff.bad <> "TRUE" OR ff.bad IS NULL)
GROUP BY "object", "filter", "date"
ORDER BY "object", "filter"
/* target_summary(object,camera,"filter",date,exposure,N,total_exposure) */;
CREATE TABLE fits_temp (
	id BIGINT, 
	"index" BIGINT, 
	file TEXT, 
	folder TEXT, 
	object TEXT, 
	"obs-date" TEXT, 
	ra TEXT, 
	dec TEXT, 
	x BIGINT, 
	y BIGINT, 
	frame_type TEXT, 
	filter TEXT, 
	focal_length TEXT, 
	exposure FLOAT, 
	camera TEXT, 
	telescope TEXT, 
	md5sum TEXT, 
	orig_folder TEXT, 
	orig_file TEXT
);
CREATE INDEX ix_fits_temp_id ON fits_temp (id);
