#  ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1
# 
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
# 
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the License.
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

from simplejson import loads

from bespin import config

_metadata_declaration = re.compile("^[^=]*=\s*")
_trailing_semi = re.compile(";*\s*$")
_leading_paren = re.compile(r"^\s*\(\s*")
_trailing_paren = re.compile(r"\s*\)\s*$")
_start_tag = re.compile(r'^\s*[\'"]define\s+metadata[\'"]\s*;*\s*$')
_end_tag = re.compile(r'^\s*[\'"]end[\'"]\s*;*\s*$')


def _parse_md_text(lines):
    """Parses the plugin metadata out of the lines of the JS file.
    """
    start = -1
    end = -1
    for i in xrange(0, len(lines)):
        if _start_tag.match(lines[i]):
            start = i
        elif _end_tag.match(lines[i]):
            end = i
            break
    
    if start == -1 or end == -1:
        return None
    
    md_text = "\n".join(lines[start+1:end])
    md_text = _metadata_declaration.sub("", md_text)
    md_text = _trailing_semi.sub("", md_text)
    md_text = _leading_paren.sub("", md_text)
    md_text = _trailing_paren.sub("", md_text)
    return md_text
    

class Plugin(object):
    def __init__(self, name, location, path_entry):
        self.name = name
        self._errors = []
        self.location = location
        self.location_name = path_entry['name']
        self.relative_location = self.location[path_entry.get("chop", 0)+1:]
    
    @property
    def errors(self):
        md = self.metadata
        return self._errors
    
    @property
    def depends(self):
        md = self.metadata
        if md:
            return md.get('depends', [])
        return []
        
    @property
    def metadata(self):
        try:
            return self._metadata
        except AttributeError:
            if self.location.isdir():
                md_path = self.location / "plugin.json"
                if not md_path.exists():
                    md = {}
                    self._errors = ["Plugin metadata file (plugin.json) file is missing"]
                    md_text = '""'
                else:
                    md_text = md_path.text()
            else:
                lines = self.location.lines()
                md_text = _parse_md_text(lines)
                
                if not md_text:
                    self._errors = ["Plugin metadata is missing or badly formatted."]
                    self._metadata = {}
                    return self._metadata
                    
            try:
                md = loads(md_text)
            except Exception, e:
                self._errors = ["Problem with metadata JSON: %s" % (e)]
                md = {}
                
            server_base_url = config.c.server_base_url
            if not server_base_url.startswith("/"):
                server_base_url = "/" + server_base_url
            name = self.name
            
            if self.location_name == "user":
                md['scripts'] = [
                    dict(url="%sgetscript/file/at/%s%%3A%s" % (
                        server_base_url, self.relative_location, 
                        scriptname),
                        id="%s:%s" % (name, scriptname))
                        for scriptname in self.scripts
                    ]
                md['stylesheets'] = [
                    dict(url="%sfile/at/%s%%3A%s" % (
                        server_base_url, self.relative_location, 
                        stylesheet),
                        id="%s:%s" % (name, stylesheet))
                    for stylesheet in self.stylesheets
                ]
            else:
                md['scripts'] = [
                    dict(url="%splugin/script/%s/%s/%s" % (
                        server_base_url, self.location_name, 
                        name, scriptname),
                        id="%s:%s" % (name, scriptname))
                        for scriptname in self.scripts
                    ]
                md['stylesheets'] = [
                    dict(url="%splugin/file/%s/%s/%s" % (
                        server_base_url, self.location_name, name, 
                        stylesheet),
                        id="%s:%s" % (name, stylesheet))
                    for stylesheet in self.stylesheets
                ]
            
            self._metadata = md
            return md

    def _putFilesInAttribute(self, attribute, glob, allowEmpty=True):
        """Finds all of the plugin files matching the given glob
        and puts them in the attribute given. If the
        attribute is already set, it is returned directly."""
        try:
            return getattr(self, attribute)
        except AttributeError:
            loc = self.location
            if loc.isdir():
                l = [loc.relpathto(f) for f in self.location.walkfiles(glob)]
            else:
                l = [] if allowEmpty else [""]
            setattr(self, attribute, l)
            return l
        
    
    @property
    def stylesheets(self):
        return self._putFilesInAttribute("_stylesheets", "*.css")
    
    @property
    def scripts(self):
        return self._putFilesInAttribute("_scripts", "*.js", 
            allowEmpty=False)
    
    def get_script_text(self, scriptname):
        """Look up the script at scriptname within this plugin."""
        if not self.location.isdir():
            return self.location.text()
            
        script_path = self.location / scriptname
        if not script_path.exists():
            return None
        
        return script_path.text()
        
                

def find_plugins(search_path=None):
    """Return plugin descriptors for the plugins on the search_path.
    If the search_path is not given, the configured plugin_path will
    be used."""
    if search_path is None:
        search_path = config.c.plugin_path
        
    result = []
    for path_entry in search_path:
        path = path_entry['path']
        for item in path.glob("*"):
            # plugins are directories with a plugin.json file or 
            # individual .js files.
            if item.isdir():
                mdfile = item / "plugin.json"
                if not mdfile.exists():
                    continue
                name = item.basename()
            elif item.ext == ".js":
                name = item.splitext()[0].basename()
            else:
                continue
                
            plugin = Plugin(name, item, path_entry)
            result.append(plugin)
    return result
    
def lookup_plugin(name, search_path=None):
    """Return the plugin descriptor for the plugin given."""
    if search_path is None:
        search_path = config.c.plugin_path
        
    for path_entry in search_path:
        path = path_entry['path']
        location = path / name
        if not location.exists():
            location = path / (name + ".js")
        if location.exists():
            if location.isdir():
                mdfile = location / "plugin.json"
                if not mdfile.exists():
                    continue
            plugin = Plugin(name, location, path_entry)
            return plugin
    
    return None