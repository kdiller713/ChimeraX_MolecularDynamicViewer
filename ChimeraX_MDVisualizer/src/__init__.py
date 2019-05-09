from chimerax.core.toolshed import BundleAPI
from chimerax.core.commands import register

from . import gui

'''
 # This is the core class to making the bundle
 # 
 # Contains methods to add commands and tools
'''
class _MyAPI(BundleAPI):

    api_version = 1

    '''
     # This creates a tool ui from this bundle
     #
     # @param session - The chimerax session being used
     # @param bundle_info - The information for this bundle
     # @param tool_info - The info for the tool
    '''
    @staticmethod
    def start_tool(session, bundle_info, tool_info):
        if tool_info.name == gui.DISPLAY_NAME:
            return gui.MolecularDynamicsTool(session, tool_info.name)
        else:
            print("Unrecognized Tool Name: " + tool_info.name)

bundle_api = _MyAPI()
