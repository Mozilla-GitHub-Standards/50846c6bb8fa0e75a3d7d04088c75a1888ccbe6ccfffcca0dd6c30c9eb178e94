#  ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1
# 
# The contents of this file are subject to the Mozilla Public License  
# Version
# 1.1 (the "License"); you may not use this file except in compliance  
# with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
# 
# Software distributed under the License is distributed on an "AS IS"  
# basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the  
# License
# for the specific language governing rights and limitations under the
# License.
# 
# The Original Code is Bespin.
# 
# The Initial Developer of the Original Code is Mozilla.
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
# 
# Contributor(s):
# 
# ***** END LICENSE BLOCK *****
# 

import re
import os
import sys

from setuptools import find_packages
from paver.setuputils import find_package_data

from paver.easy import *
from paver import setuputils
setuputils.install_distutils_tasks()


execfile(os.path.join('bespin', '__init__.py'))

options(
    staticdir="",
    server_base_url="/",
    setup=Bunch(
        name="BespinServer",
        version=VERSION,
        packages=find_packages(),
        package_data=find_package_data('bespin', 'bespin', 
                                only_in_packages=False),
        entry_points="""
[console_scripts]
bespin_worker=bespin.queue:process_queue
queue_stats=bespin.queuewatch:command
telnet_mobwrite=bespin.mobwrite.mobwrite_daemon:process_mobwrite
bespin_mobwrite=bespin.mobwrite.mobwrite_web:start_server
"""
    ),
    server=Bunch(
        # set to true to allow connections from other machines
        address="",
        port=8080,
        try_build=False,
        dburl=None,
        async=False,
        config_file=path("devconfig.py")
    )
)

@task
def install_dependencies():
    """Install the necessary Python packages."""
    sh("easy_install ext/pip-0.4.1.tar.gz")
    sh("pip install -r requirements.txt")
    
@task
def create_db():
    """Creates the development database"""
    from bespin import config, database, db_versions
    from migrate.versioning.shell import main
    
    config.set_profile('dev')
    
    base_url = config.c.dburl
    
    config_file = options.server.config_file
    if config_file.exists():
        info("Loading config: %s", config_file)
        code = compile(config_file.bytes(), config_file, "exec")
        exec code in {}

    if config.c.dburl == base_url and path("devdata.db").exists():
        raise BuildFailure("Development database already exists")
    
    config.activate_profile()
    dry("Create database tables", database.Base.metadata.create_all, bind=config.c.dbengine)
    
    repository = str(path(db_versions.__file__).dirname())
    dburl = config.c.dburl
    result = sh("python bespin/db_versions/manage.py version", capture=True)
    dry("Turn on migrate versioning", main, ["version_control", "--version", result.rstrip(), dburl, repository])


@task
@needs(['setuptools.command.develop', 'install_dependencies'])
def develop():
    """After installing dependencies, creates schema for the development
    database."""
    info("""The software is now installed. If this is your first time, you will probably
also want to create your development database with this command:

paver create_db
""")

@task
def start():
    """Starts the BespinServer on localhost port 8080 for development.
    
    You can change the port and allow remote connections by setting
    server.port or server.address on the command line.
    
    paver server.address=your.ip.address server.port=8000 start
    
    will allow remote connections (assuming you don't have a firewall
    blocking the connection) and start the server on port 8000.
    """
    from bespin import config, controllers
    from paste.httpserver import serve
    
    options.order('server')
    
    config.set_profile('dev')
    
    if options.staticdir:
        config.c.static_dir = path(options.clientdir) / options.staticdir
    
    if options.server.dburl:
        config.c.dburl = options.server.dburl
    
    if options.server.async:
        config.c.async_jobs = True
    
    config.c.server_base_url = options.server_base_url
    
    config_file = options.server.config_file
    if config_file.exists():
        info("Loading config: %s", config_file)
        code = compile(config_file.bytes(), config_file, "exec")
        exec code in {}
    
    config.activate_profile()
    port = int(options.port)
    serve(controllers.make_app(), options.address, port, use_threadpool=True)

@task
@needs(['sdist'])
def production():
    """Gets things ready for production."""
    non_production_packages = set(["py", "WebTest", "boto", "virtualenv", 
                                  "Paver", "nose", "growl",
                                  "path", "httplib2", "Jinja2", "Markdown",
                                  "MySQL-python"])
    production = path("production")
    production_requirements = production / "requirements.txt"
    
    libs_dest = production / "libs"
    libs_dest.rmtree()
    libs_dest.mkdir()
    
    sdist_file = path("dist/BespinServer-%s.tar.gz" % options.version)
    sdist_file.move(libs_dest)
    
    ext_dir = path("ext")
    external_libs = []
    for f in ext_dir.glob("*"):
        f.copy(libs_dest)
        name = f.basename()
        name = name[:name.index("-")]
        non_production_packages.add(name)
        external_libs.append("libs/%s" % (f.basename()))
        
    lines = production_requirements.lines() if production_requirements.exists() else []
    
    requirement_pattern = re.compile(r'^(.*)==')
    
    i = 0
    found_packages = set()
    while i < len(lines):
        if lines[i].startswith("-e "):
            del lines[i]
            continue
            
        rmatch = requirement_pattern.match(lines[i])
        if rmatch:
            name = rmatch.group(1)
            found_packages.add(name)
            deleted = False
            for npp in non_production_packages:
                if name == npp:
                    del lines[i]
                    deleted = True
                    break
            if deleted:
                continue
        i+=1
    
    lines.append("libs/BespinServer-%s.tar.gz" % options.version)
    lines.append("libs/dryice-%s.tar.gz" % options.version)
    
    
    # path.py doesn't install properly via pip/easy_install
    lines.append("http://pypi.python.org/packages/source/p/path.py/"
        "path-2.2.zip#md5=941660081788282887f652510d80e64e")
        
    lines.append("http://httplib2.googlecode.com/files/httplib2-0.4.0.tar.gz")
    
    lines.append("http://pypi.python.org/packages/source/"
        "M/MySQL-python/MySQL-python-1.2.3c1.tar.gz")
    
    lines.extend(external_libs)
    production_requirements.write_lines(lines)
    
    call_pavement("production/pavement.py", "bootstrap")
    
@task
@cmdopts([('user=', 'u', 'User to set up for Bespin editing')])
def editbespin(options):
    """Use Bespin to edit Bespin. This will change the given
    user's file location to the directory above Bespin, allowing
    you to edit Bespin (and any other projects you have
    in that directory)."""
    
    if not 'editbespin' in options or not options.editbespin.user:
        raise BuildFailure("You must specify a user with -u for this task.")
        
    user = options.editbespin.user
    
    from bespin import config
    from bespin import database, filesystem
    from sqlalchemy.orm.exc import NoResultFound
    
    config.set_profile("dev")
    config.activate_profile()
    session = config.c.session_factory()
    try:
        user = session.query(database.User).filter_by(username=user).one()
    except NoResultFound:
        raise BuildFailure("I couldn't find %s in the database. Sorry!" % (user))
    
    location = path.getcwd().parent.abspath()
    user.file_location = location
    user.recompute_files()
    session.commit()
    bespinsettings_loc = location / "BespinSettings"
    if not bespinsettings_loc.exists():
        project = filesystem.get_project(user, user, "BespinSettings", create=True)
        project.install_template('usertemplate')
    info("User %s set up to access directory %s" % (user, location))

@task
def upgrade():
    """Upgrade your database."""
    from bespin import config, model, db_versions
    from migrate.versioning.shell import main
    config.set_profile('dev')
    config.activate_profile()
    repository = str(path(db_versions.__file__).dirname())
    dburl = config.c.dburl
    dry("Run the database upgrade", main, ["upgrade", dburl, repository])

@task
def try_upgrade():
    """Run SQLAlchemy-migrate test on your database."""
    from bespin import config, model, db_versions
    from migrate.versioning.shell import main
    config.set_profile('dev')
    config.activate_profile()
    repository = str(path(db_versions.__file__).dirname())
    dburl = config.c.dburl
    dry("Test the database upgrade", main, ["test", repository, dburl])

