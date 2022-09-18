# fits_cataloger
Simple utility to catalog and store astrophotographic fits images.

Usage:
  1. (optional but recommended) Create python virtual environment
    
          python3 -m virtualenv venv
    
  2. Install python dependencies from requirements.txt (activate your virtual environment first!)

          source venv/bin/activate
          pip3 install -r requirements.txt

  3. Edit fitcat.py to define folders and information relating to cameras & telescopes

          quarantine_dir = "/path/to/your/quarantine"				# define absolute path to your quarantine folder
          image_dir = "/path/to/your/images" 						    # define absolute path to folder where you wish to store images
          library_db = "/path/to/your/database.db"				  # define absolute path to sqlite3 database file that will store data about your images
          restore_folder = "/path/to/a/temporary/folder"		# used only if you need to roll back changes (manual process)
          
          CAMERAS = [ ['CAMERA 1', x_pixels, y_pixels ], ['CAMERA 2', x_pixels, y_pixels] ]
          TELESCOPES = [ ['SCOPE 1', focal_length], ['SCOPE 2', focal_length] ]   

  4. (optional but HIGHLY recommended) Create backup of your image files prior to first use

  5. Run from command line
  
          python3 fitcat.py
  
  
  
  Some obvious limitations in above - the script assumes that your telescopes have unique focal lengths and cameras have unique resolutions.  If you have more than one camera with the same resolution, or if you have more than one telescope with the same focal length you will need to modify the code appropriately.
  
  This script actively moves files on your hard drive and deletes folders in an attempt to keep your file system clean.  Use at your own risk!
