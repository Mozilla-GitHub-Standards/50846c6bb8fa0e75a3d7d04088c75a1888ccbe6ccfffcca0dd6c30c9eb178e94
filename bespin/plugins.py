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
                else:
                    md_text = md_path.text()
            else:
                lines = self.location.lines()
                start = -1
                end = -1
                for i in xrange(0, len(lines)):
                    if "// ---plugin.json---" in lines[i]:
                        start = i
                    elif "// ---" in lines[i]:
                        end = i
                        break
                
                if start == -1 or end == -1:
                    self._errors = ["Plugin metadata is missing or badly formatted."]
                    self._metadata = {}
                    return self._metadata
                    
                md_text = "\n".join(lines[start+1:end])
                md_text = _metadata_declaration.sub("", md_text)
                md_text = _trailing_semi.sub("", md_text)
                
            try:
                md = loads(md_text)
            except Exception, e:
                self._errors = ["Problem with metadata JSON: %s" % (e)]
                md = {}
                
            self._metadata = md
            return md
            
    @property
    def scripts(self):
        try:
            return self._scripts
        except AttributeError:
            loc = self.location
            if loc.isdir():
                scripts = [loc.relpathto(f) for f in self.location.walkfiles("*.js")]
            else:
                scripts = [""]
            self._scripts = scripts
            return scripts
    
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
            plugin = Plugin(name, location, path_entry)
            return plugin
    
    return None