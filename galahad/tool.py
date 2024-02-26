import inspect
import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from gp import GPTask
from IPython.display import display
from ipywidgets import Output
from .dataset import GalaxyDatasetWidget
from nbtools import NBTool, UIBuilder, UIOutput, python_safe, EventManager
from .utils import GALAXY_LOGO, session_color, server_name, galaxy_url


class GalaxyToolWidget(UIBuilder):
    """A widget for representing the status of a GenePattern job"""
    session_color = None
    tool = None
    function_wrapper = None
    parameter_spec = None
    upload_callback = None
    kwargs = {}

    def create_function_wrapper(self, tool):
        """Create a function that accepts the expected input and submits a Galaxy job"""

        if tool is None or tool.gi is None: return lambda: None  # Dummy function for null task
        name_map = {}  # Map of Python-safe parameter names to Galaxy parameter names

        # Function for submitting a new Galaxy job based on the task form
        def submit_job(**kwargs):
            spec = GalaxyToolWidget.make_job_spec(tool, **kwargs)
            history = tool.gi.histories.list()[0]  # TODO: Fix in a way that supports non-default histories
            datasets = tool.run(spec, history)
            for dataset in datasets:
                display(GalaxyDatasetWidget(dataset, logo='none', color=session_color(galaxy_url(tool.gi), secondary_color=True)))

        # Function for adding a parameter with a safe name
        def add_param(param_list, p):
            safe_name = python_safe(p['name'])
            name_map[safe_name] = p['name']
            param = inspect.Parameter(safe_name, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            param_list.append(param)

        # Generate function signature programmatically
        submit_job.__qualname__ = tool.name
        submit_job.__doc__ = tool.wrapped['description']
        params = []
        for p in tool.wrapped['inputs']: add_param(params, p)  # Loop over all parameters
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
        if task_param['type'] == 'data':
            param_spec['type'] = 'file'
            if task_param['multiple']: param_spec['maximum'] = 100
        elif task_param['type'] == 'select':
            param_spec['type'] = 'choice'
            param_spec['choices'] = {c[0]: c[1] for c in task_param['options']}
            if task_param['textable']: param_spec['combo'] = True
            if task_param['multiple']: param_spec['multiple'] = True
        # elif task_param.attributes['type'] == 'java.lang.Integer': param_spec['type'] = 'number'
        # elif task_param.attributes['type'] == 'java.lang.Float': param_spec['type'] = 'number'
        # elif task_param.attributes['type'].lower() == 'password': param_spec['type'] = 'password'
        else: param_spec['type'] = 'text'

    @staticmethod
    def override_if_set(safe_name, attr, param_overrides, param_val):
        if param_overrides and safe_name in param_overrides and attr in param_overrides[safe_name]:
            return param_overrides[safe_name][attr]
        else: return param_val

    def create_param_spec(self, tool, kwargs):
        """Create the display spec for each parameter"""
        if tool is None: return {}  # Dummy function for null task
        spec = {}
        param_overrides = kwargs.pop('parameters', None)
        for p in tool.wrapped['inputs']:
            safe_name = python_safe(p['name'])
            spec[safe_name] = {}
            spec[safe_name]['name'] = GalaxyToolWidget.form_value(
                GalaxyToolWidget.override_if_set(safe_name, 'name', param_overrides, p['label'])
            )
            spec[safe_name]['default'] = GalaxyToolWidget.form_value(
                GalaxyToolWidget.override_if_set(safe_name, 'default', param_overrides, p['value'])
            )
            spec[safe_name]['description'] = GalaxyToolWidget.form_value(
                GalaxyToolWidget.override_if_set(safe_name, 'description', param_overrides, p['help'])
            )
            spec[safe_name]['optional'] = GalaxyToolWidget.override_if_set(safe_name, 'optional', param_overrides,
                                                                           p['optional'] if 'optional' in p else False)
            spec[safe_name]['kinds'] = GalaxyToolWidget.override_if_set(safe_name, 'kinds', param_overrides,
                                                                        p['extensions'] if 'extensions' in p else [])
            self.add_type_spec(p, spec[safe_name])
        return spec

    @staticmethod
    def extract_parameter_groups(task):
        groups = task.param_groups if hasattr(task, 'param_groups') else param_groups(task)     # Get param groups
        job_options_group = task.job_group if hasattr(task, 'job_group') else job_group(task)   # Get job options
        job_options_group['advanced'] = True                                                    # Hide by default
        all_groups = groups + [job_options_group]                                               # Join groups
        for group in all_groups:                                                                # Escape param names
            if 'parameters' in group:
                for i in range(len(group['parameters'])):
                    group['parameters'][i] = python_safe(group['parameters'][i])
        return all_groups

    def generate_upload_callback(self):
        """Create an upload callback to pass to file input widgets"""
        def genepattern_upload_callback(values):
            try:
                for k in values:
                    path = os.path.realpath(k)
                    gpfile = self.tool.server_data.upload_file(k, path)
                    os.remove(path)
                    return gpfile.get_url()
            except Exception as e:
                self.error = f"Error encountered uploading file: {e}"
        return genepattern_upload_callback

    def handle_error_task(self, error_message, name='GenePattern Module', **kwargs):
        """Display an error message if the task is None"""
        ui_args = {'color': session_color(), **kwargs}
        UIBuilder.__init__(self, lambda: None, **ui_args)

        self.name = name
        self.display_header = False
        self.display_footer = False
        self.error = error_message

    def load_tool_inputs(self):
        if 'inputs' not in self.tool.wrapped:
            self.tool = self.tool.gi.tools.get(self.tool.id, io_details=True)

    def __init__(self, tool=None, origin='', id='', **kwargs):
        """Initialize the tool widget"""
        # TODO: Reimplement
        self.tool = tool
        self.kwargs = kwargs
        if tool and origin is None: origin = galaxy_url(tool.gi)
        if tool and id is None: id = tool.id

        # Set the right look and error message if tool is None
        if self.tool is None or self.tool.gi is None:
            self.handle_error_task('No Galaxy tool specified.', **kwargs)
            return

        self.load_tool_inputs()
        self.function_wrapper = self.create_function_wrapper(self.tool)     # Create run tool function
        self.parameter_spec = self.create_param_spec(self.tool, kwargs)     # Create the parameter spec
        self.session_color = session_color(galaxy_url(tool.gi))             # Set the session color
        ui_args = {                                                         # Assemble keyword arguments
            'color': self.session_color,
            'id': id,
            'logo': GALAXY_LOGO,
            'origin': origin,
            'name': tool.name,
            'description': tool.wrapped['description'],
            # 'parameter_groups': GalaxyToolWidget.extract_parameter_groups(self.tool),
            'parameters': self.parameter_spec,
            'subtitle': f'Version {tool.version}',
            'upload_callback': self.generate_upload_callback(),
        }
        ui_args = { **ui_args, **kwargs }                                   # Merge kwargs (allows overrides)
        UIBuilder.__init__(self, self.function_wrapper, **ui_args)          # Initiate the widget

    @staticmethod
    def form_value(raw_value):
        """Give the default parameter value in format the UI Builder expects"""
        if raw_value is not None: return raw_value
        else: return ''


class GalaxyTool(NBTool):
    """Tool wrapper for Galaxy tools"""

    def __init__(self, server_name, tool):
        NBTool.__init__(self)
        self.origin = server_name
        self.id = tool.id
        self.name = tool.name
        self.description = tool.wrapped['description']
        self.load = lambda **kwargs: GalaxyToolWidget(tool, id=self.id, origin=self.origin, **kwargs)
