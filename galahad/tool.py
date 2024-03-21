import inspect
import json
import os
from IPython.display import display
from ast import literal_eval
from bioblend import ConnectionError
from bioblend.galaxy.objects import Tool
from nbtools import NBTool, UIBuilder, python_safe, Data, DataManager
from .dataset import GalaxyDatasetWidget
from .utils import GALAXY_LOGO, session_color, galaxy_url, server_name


class GalaxyToolWidget(UIBuilder):
    """A widget representing a Galaxy tool"""
    session_color = None
    tool = None
    function_wrapper = None
    parameter_spec = None
    upload_callback = None
    kwargs = {}

    def create_function_wrapper(self, all_params):
        """Create a function that accepts the expected input and submits a Galaxy job"""
        if self.tool is None or self.tool.gi is None: return lambda: None  # Dummy function for null task
        name_map = {}  # Map of Python-safe parameter names to Galaxy parameter names

        # Function for submitting a new Galaxy job based on the task form
        def submit_job(**kwargs):
            spec = GalaxyToolWidget.make_job_spec(self.tool, **kwargs)
            history = self.tool.gi.histories.list()[0]  # TODO: Fix in a way that supports non-default histories
            try:
                datasets = self.tool.run(spec, history)
                for dataset in datasets:
                    display(GalaxyDatasetWidget(dataset, logo='none', color=session_color(galaxy_url(self.tool.gi), secondary_color=True)))
            except ConnectionError as e:
                error = json.loads(e.body)['err_msg'] if hasattr(e, 'body') else f'Unknown error running Galaxy tool: {e}'
                display(GalaxyDatasetWidget(None, logo='none', name='Galaxy Error', error=error, color=session_color(galaxy_url(self.tool.gi), secondary_color=True)))
            except Exception as e:
                display(GalaxyDatasetWidget(None, logo='none', name='Galaxy Error', error=f'Unknown Error: {e}', color=session_color(galaxy_url(self.tool.gi), secondary_color=True)))

        # Function for adding a parameter with a safe name
        def add_param(param_list, p):
            safe_name = python_safe(p['name'])
            name_map[safe_name] = p['name']
            param = inspect.Parameter(safe_name, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            param_list.append(param)

        # Generate function signature programmatically
        submit_job.__qualname__ = self.tool.name
        submit_job.__doc__ = self.tool.wrapped['description']
        params = []
        for p in all_params: add_param(params, p)  # Loop over all parameters
        submit_job.__signature__ = inspect.Signature(params)

        return submit_job

    @staticmethod
    def make_job_spec(tool, **kwargs):
        for i in tool.wrapped['inputs']:
            if i['type'] == 'data':
                id = kwargs[i['name']]
                kwargs[i['name']] = {'id': id, 'src': 'hda'}
        return kwargs

    def add_type_spec(self, task_param, param_spec):
        if   task_param['type'] == 'select':            param_spec['type'] = 'choice'
        elif task_param['type'] == 'hidden':            param_spec['type'] = 'text'
        elif task_param['type'] == 'upload_dataset':    param_spec['type'] = 'file'     # TODO: Verify
        elif task_param['type'] == 'genomebuild':       param_spec['type'] = 'choice'   # TODO: Verify
        elif task_param['type'] == 'conditional':       param_spec['type'] = 'text'     # TODO: Implement sub-parameters
        elif task_param['type'] == 'baseurl':           param_spec['type'] = 'text'
        elif task_param['type'] == 'data':              param_spec['type'] = 'file'     # TODO: Verify
        elif task_param['type'] == 'text':              param_spec['type'] = 'text'
        elif task_param['type'] == 'boolean':           param_spec['type'] = 'choice'   # TODO: Verify
        elif task_param['type'] == 'directory_uri':     param_spec['type'] = 'text'     # TODO: Verify
        elif task_param['type'] == 'data_collection':   param_spec['type'] = 'file'     # TODO: Verify
        elif task_param['type'] == 'repeat':            param_spec['type'] = 'text'     # TODO: Implement sub-parameters
        elif task_param['type'] == 'rules':             param_spec['type'] = 'text'     # TODO: Verify
        elif task_param['type'] == 'data_column':       param_spec['type'] = 'choice'   # TODO: Verify
        elif task_param['type'] == 'integer':           param_spec['type'] = 'number'
        elif task_param['type'] == 'float':             param_spec['type'] = 'number'
        elif task_param['type'] == 'hidden_data':       param_spec['type'] = 'file'     # TODO: Verify
        elif task_param['type'] == 'color':             param_spec['type'] = 'color'
        elif task_param['type'] == 'drill_down':        param_spec['type'] = 'choice'   # TODO: Verify
        else: param_spec['type'] = 'text'

        # Set parameter attributes
        if 'optional' in task_param and task_param['optional']: param_spec['optional'] = True
        if 'multiple' in task_param and task_param['multiple']: param_spec['multiple'] = True
        if 'multiple' in task_param and task_param['multiple']: param_spec['maximum'] = 100
        if 'textable' in task_param and task_param['textable']: param_spec['combo'] = True
        if 'hidden' in task_param and task_param['hidden']: param_spec['hide'] = True
        if 'extensions' in task_param: param_spec['kinds'] = task_param['extensions']
        if 'options' in task_param: param_spec['choices'] = GalaxyToolWidget.options_spec(task_param['options'])

        # Special case for booleans
        if task_param['type'] == 'boolean' and 'options' not in task_param:
            param_spec['choices'] = {'Yes': 'True', 'No': 'False'}

        # Special case for multi-value select inputs
        if param_spec['type'] == 'choice' and param_spec.get('multiple'):
            if isinstance(param_spec['default'], str): param_spec['default'] = literal_eval(param_spec['default'])
            if param_spec['default'] is None or param_spec['default'] == 'None': param_spec['default'] = []

        # TODO: Notes on parameter support
        #   drill_down: Works, but not particularly useful without dynamic refresh support
        #   hidden_data: Appears to be fine, but not testable as it only is used in the cufflinks tool, which
        #       won't run without "conditional" parameter support.
        #   data_column: Works, but not as useful without dynamic refresh support
        #   rules: Entirely unsupported. Looks complicated to implement. Only used in "Apply rules" tool.
        #   data_collection: Works. Tested with "Unzip collection" tool.
        #   directory_uri: Entirely unsupported. Looks complicated to implement. Only used in "Export datasets" tool.
        #   boolean: Works.
        #   genomebuild: Unknown. Only used in "Data Fetch" tool, which doesns't appear in usegalaxy.org UI.
        #   upload_dataset: Unknown. Only used in "Data Fetch" tool, which doesns't appear in usegalaxy.org UI.

        # TODO: Implement dynamic refresh for certain types (drill_down, data_column, etc.)

    @staticmethod
    def options_spec(options):
        if isinstance(options, list): return { c[0]: c[1] for c in options }
        else:
            choices = {}
            for l in options.values():
                for i in l: choices[i['name']] = i['id']
            return choices

    @staticmethod
    def override_if_set(safe_name, attr, param_overrides, param_val):
        if param_overrides and safe_name in param_overrides and attr in param_overrides[safe_name]:
            return param_overrides[safe_name][attr]
        else: return param_val

    @staticmethod
    def value_strings(raw_values):
        if isinstance(raw_values, dict):
            if 'values' in raw_values and isinstance(raw_values['values'], list):
                if not len(raw_values['values']): return []
                elif 'id' in raw_values['values'][0]:
                    return [v['id'] for v in raw_values['values']]
        return str(raw_values)

    def create_param_spec(self, kwargs):
        """Create the display spec for each parameter"""
        if self.tool is None or self.tool.gi is None or self.all_params is None: return {}  # Dummy function for null task
        spec = {}
        param_overrides = kwargs.pop('parameters', None)
        for p in self.all_params:
            safe_name = python_safe(p['name'])
            spec[safe_name] = {}
            spec[safe_name]['name'] = GalaxyToolWidget.form_value(
                GalaxyToolWidget.override_if_set(safe_name, 'name', param_overrides, p['label'] if p.get('label') else p['name'])
            )
            spec[safe_name]['default'] = GalaxyToolWidget.form_value(
                GalaxyToolWidget.override_if_set(safe_name, 'default', param_overrides,
                                                 GalaxyToolWidget.value_strings(p['value']) if 'value' in p else '')
            )
            spec[safe_name]['description'] = GalaxyToolWidget.form_value(
                GalaxyToolWidget.override_if_set(safe_name, 'description', param_overrides, p['help'] if 'help' in p else '')
            )
            spec[safe_name]['optional'] = GalaxyToolWidget.override_if_set(safe_name, 'optional', param_overrides,
                                                                           p['optional'] if 'optional' in p else False)
            spec[safe_name]['kinds'] = GalaxyToolWidget.override_if_set(safe_name, 'kinds', param_overrides,
                                                                        p['extensions'] if 'extensions' in p else [])
            self.add_type_spec(p, spec[safe_name])

        return spec

    @staticmethod
    def generate_upload_callback(session, widget):
        """Create an upload callback to pass to data inputs"""
        def galaxy_upload_callback(values):
            try:
                for k in values:
                    # Get the full path in the workspace
                    path = os.path.realpath(k)

                    # Get the history and upload to that history
                    history = session.histories.list()[0]  # TODO: Use selected history
                    dataset = history.upload_dataset(path)

                    # Remove the uploaded file from the workspace
                    os.remove(path)

                    # Register the uploaded file with the data manager
                    kind = dataset.wrapped['extension'] if 'extension' in dataset.wrapped else ''
                    data = Data(origin=server_name(galaxy_url(session)), group=history.name, uri=dataset.id,
                                label=dataset.name, kind=kind)
                    def create_dataset_lambda(id): return lambda: GalaxyDatasetWidget(id)
                    DataManager.instance().data_widget(origin=data.origin, uri=data.uri,
                                                       widget=create_dataset_lambda(dataset.id))
                    DataManager.instance().register(data)

                    return dataset.id
            except Exception as e:
                widget.error = f"Error encountered uploading file: {e}"
        return galaxy_upload_callback

    def handle_error_task(self, error_message, name='Galaxy Tool', **kwargs):
        """Display an error message if the tool is None"""
        ui_args = {'color': session_color(), **kwargs}
        UIBuilder.__init__(self, lambda: None, **ui_args)

        self.name = name
        self.display_header = False
        self.display_footer = False
        self.error = error_message

    def load_tool_inputs(self):
        if 'inputs' not in self.tool.wrapped:
            tool_json = self.tool.gi.gi.tools.build(
                # TODO: Use selected history
                tool_id=self.tool.id, history_id=self.tool.gi.gi.histories.get_most_recently_used_history()['id'])
            self.tool = Tool(wrapped=tool_json, parent=self.tool.parent, gi=self.tool.gi)

    def __init__(self, tool=None, origin='', id='', **kwargs):
        """Initialize the tool widget"""
        self.tool = tool
        self.kwargs = kwargs
        if tool and origin is None: origin = galaxy_url(tool.gi)
        if tool and id is None: id = tool.id

        # Set the right look and error message if tool is None
        if self.tool is None or self.tool.gi is None:
            self.handle_error_task('No Galaxy tool specified.', **kwargs)
            return

        self.load_tool_inputs()
        self.parameter_groups, self.all_params = self.expand_sections()         # List groups and compile all params
        self.function_wrapper = self.create_function_wrapper(self.all_params)   # Build the function wrapper
        self.parameter_spec = self.create_param_spec(kwargs)                    # Create the parameter spec
        self.session_color = session_color(galaxy_url(tool.gi))                 # Set the session color
        ui_args = {                                                             # Assemble keyword arguments
            'color': self.session_color,
            'id': id,
            'logo': GALAXY_LOGO,
            'origin': origin,
            'name': tool.name,
            'description': tool.wrapped['description'],
            'parameter_groups': self.parameter_groups,
            'parameters': self.parameter_spec,
            'subtitle': f'Version {tool.version}',
            'upload_callback': self.generate_upload_callback(self.tool.gi, self),
        }
        ui_args = { **ui_args, **kwargs }                                   # Merge kwargs (allows overrides)
        UIBuilder.__init__(self, self.function_wrapper, **ui_args)          # Initiate the widget
        self.attach_help_section()

    def expand_sections(self, inputs=None):
        if not self.tool or not self.tool.wrapped or 'inputs' not in self.tool.wrapped: return [], []
        if not inputs: inputs = self.tool.wrapped['inputs']

        groups = []
        params = []
        for p in inputs:
            # TODO: Add support for conditional and repeat params
            if p['type'] == 'section':
                if 'inputs' in p:
                    section_groups, section_params = self.expand_sections(p['inputs'])
                    groups += section_groups
                    params += section_params

                groups.append({
                    'name': p['label'] if 'label' in p else (p['title'] if 'title' in p else p['name']),
                    'description': p['help'] if 'help' in p else '',
                    'hidden': (not p['expanded']) if 'expanded' in p else False,
                    'parameters': [i['name'] for i in p['inputs']]  # [(python_safe(i['label']) if 'label' in i else python_safe(i['name'])) for i in p['inputs']]
                })
            else: params.append(p)
        return groups, params

    @staticmethod
    def form_value(raw_value):
        """Give the default parameter value in format the UI Builder expects"""
        if raw_value is not None: return raw_value
        else: return ''

    def attach_help_section(self):
        self.extra_menu_items = {**self.extra_menu_items, **{'Display Help': {
                'action': 'method',
                'code': 'display_help'
            }}}

    def display_help(self):
        self.info = self.tool.wrapped['help']


class GalaxyTool(NBTool):
    """Tool wrapper for Galaxy tools"""

    def __init__(self, server_name, tool):
        NBTool.__init__(self)
        self.origin = server_name
        self.id = tool.id
        self.name = tool.name
        self.description = tool.wrapped['description']
        self.load = lambda **kwargs: GalaxyToolWidget(tool, id=self.id, origin=self.origin, **kwargs)


class GalaxyUploadTool(NBTool):
    """Tool wrapper for Galaxy uploads"""

    class GalaxyUploadWidget(UIBuilder):
        def __init__(self, tool, session, **kwargs):
            self.session = session
            ui_args = {
                'color': session_color(galaxy_url(session)),
                'id': tool.id,
                'logo': GALAXY_LOGO,
                'origin': tool.origin,
                'name': tool.name,
                'description': tool.description,
                'parameters': {'dataset': {'type': 'file', 'description': 'Select a file to upload to the Galaxy server'}},
                'upload_callback': GalaxyToolWidget.generate_upload_callback(session, self),
                **kwargs
            }
            UIBuilder.__init__(self, self.create_function_wrapper(), **ui_args)

        def create_function_wrapper(self):
            def upload_data(dataset):
                display(GalaxyDatasetWidget(dataset, logo='none', color=session_color(galaxy_url(self.session), secondary_color=True)))
            return upload_data

    def __init__(self, server_name, session):
        NBTool.__init__(self)
        self.origin = server_name
        self.id = 'data_upload_tool'
        self.name = 'Upload Data'
        self.description = 'Upload data files to Galaxy server'
        self.load = lambda **kwargs: GalaxyUploadTool.GalaxyUploadWidget(self, session)
