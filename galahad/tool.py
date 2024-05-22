import inspect
import json
import os
from copy import deepcopy
from IPython.display import display
from bioblend import ConnectionError
from bioblend.galaxy.objects import Tool, HistoryDatasetAssociation
from nbtools import NBTool, UIBuilder, python_safe, Data, DataManager
from nbtools.uibuilder import UIBuilderBase
from nbtools.utils import is_url

from .dataset import GalaxyDatasetWidget
from .utils import (GALAXY_LOGO, session_color, galaxy_url, server_name, data_icon, poll_data_and_update,
                    current_history, limited_eval, is_id, walk_tree)


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

        # Function for submitting a new Galaxy job based on the task form
        def submit_job(**kwargs):
            spec = self.make_job_spec(self.tool, **kwargs)
            history = current_history(self.tool.gi)
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
            safe_name = python_safe(p.get('py_name', p['name']))
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
    def is_excluded(param, kwargs):
        if param.get('conditional_display') is None: return False
        if kwargs.get(param['conditional_param']) != param['conditional_display']: return True
        else: return False

    def make_job_spec(self, tool, **kwargs):
        for i in self.all_params:
            # Fix parameter names to expected Galaxy values
            galaxy_name = i.get('galaxy_name', i['name'])
            if i['py_name'] != galaxy_name:
                kwargs[galaxy_name] = kwargs[i['py_name']]
                del kwargs[i['py_name']]

            # Ensure select parameter values don't resolve to None
            if i['type'] == 'select' and kwargs[galaxy_name] is None: kwargs[galaxy_name] = ''

            # Remove repeat parent parameters
            if i['type'] == 'repeat': del kwargs[galaxy_name]

            # Prepare data parameters
            if i['type'] == 'data':
                id = kwargs[galaxy_name]
                if id is not None:
                    if is_url(id):
                        dataset_json = self.tool.gi.gi.tools.put_url(content=id, history_id=current_history(self.tool.gi).id)
                        id = dataset_json['outputs'][0]['id']
                    kwargs[galaxy_name] = {'id': id, 'src': 'hda'}

        return kwargs

    def add_type_spec(self, task_param, param_spec):
        if   task_param['type'] == 'select':            param_spec['type'] = 'choice'
        elif task_param['type'] == 'hidden':            param_spec['type'] = 'text'
        elif task_param['type'] == 'upload_dataset':    param_spec['type'] = 'file'
        elif task_param['type'] == 'genomebuild':       param_spec['type'] = 'choice'
        elif task_param['type'] == 'baseurl':           param_spec['type'] = 'text'
        elif task_param['type'] == 'data':              param_spec['type'] = 'file'
        elif task_param['type'] == 'text':              param_spec['type'] = 'text'
        elif task_param['type'] == 'boolean':           param_spec['type'] = 'choice'
        elif task_param['type'] == 'directory_uri':     param_spec['type'] = 'text'
        elif task_param['type'] == 'data_collection':   param_spec['type'] = 'file'
        elif task_param['type'] == 'repeat':            param_spec['type'] = 'number'
        elif task_param['type'] == 'rules':             param_spec['type'] = 'text'
        elif task_param['type'] == 'data_column':       param_spec['type'] = 'choice'
        elif task_param['type'] == 'integer':           param_spec['type'] = 'number'
        elif task_param['type'] == 'float':             param_spec['type'] = 'number'
        elif task_param['type'] == 'hidden_data':       param_spec['type'] = 'file'
        elif task_param['type'] == 'color':             param_spec['type'] = 'color'
        elif task_param['type'] == 'drill_down':        param_spec['type'] = 'choice'
        else: param_spec['type'] = 'text'

        # Set parameter attributes
        if 'optional' in task_param and task_param['optional']: param_spec['optional'] = True
        if 'multiple' in task_param and task_param['multiple'] and param_spec['type'] != 'file': param_spec['multiple'] = True
        if 'multiple' in task_param and task_param['multiple'] and param_spec['type'] != 'file': param_spec['maximum'] = 100
        if 'textable' in task_param and task_param['textable']: param_spec['combo'] = True
        if 'hidden' in task_param and task_param['hidden']: param_spec['hide'] = True
        if 'extensions' in task_param: param_spec['kinds'] = task_param['extensions']
        if 'options' in task_param: param_spec['choices'] = GalaxyToolWidget.options_spec(task_param['options'])

        # Special case for booleans
        if task_param['type'] == 'boolean' and 'options' not in task_param:
            param_spec['choices'] = {'Yes': 'True', 'No': 'False'}

        # Special case for multi-value select inputs
        if param_spec['type'] == 'choice' and param_spec.get('multiple'):
            if isinstance(param_spec['default'], str): param_spec['default'] = limited_eval(param_spec['default'])
            if param_spec['default'] is None or param_spec['default'] == 'None': param_spec['default'] = []

        # Special case for repeat parameters
        if task_param['type'] == 'repeat': param_spec['default'] = task_param.get('value', task_param['default'])

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
        param_overrides = kwargs.get('parameters', None)
        for p in self.all_params:
            safe_name = p.get('py_name', python_safe(p['name']))
            spec[safe_name] = {}
            spec[safe_name]['name'] = GalaxyToolWidget.form_value(
                GalaxyToolWidget.override_if_set(safe_name, 'name', param_overrides, p['label'] if p.get('label') else p['name'])
            )
            spec[safe_name]['default'] = GalaxyToolWidget.form_value(
                GalaxyToolWidget.override_if_set(safe_name, 'default', param_overrides,
                                                 GalaxyToolWidget.value_strings(p.get('value') if p.get('value') is not None else ''))
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
                    history = current_history(session)
                    dataset = history.upload_dataset(path)

                    # Remove the uploaded file from the workspace
                    os.remove(path)

                    # Register the uploaded file with the data manager
                    kind = 'error' if dataset.state == 'error' else (dataset.wrapped['extension'] if 'extension' in dataset.wrapped else '')
                    data = Data(origin=server_name(galaxy_url(session)), group=history.name, uri=dataset.id,
                                label=dataset.name, kind=kind, icon=data_icon(dataset.state))
                    def create_dataset_lambda(id): return lambda: GalaxyDatasetWidget(id)
                    DataManager.instance().data_widget(origin=data.origin, uri=data.uri,
                                                       widget=create_dataset_lambda(dataset.id))
                    DataManager.instance().register(data)
                    poll_data_and_update(dataset)

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
                tool_id=self.tool.id, history_id=current_history(self.tool.gi).id)
            self.tool = Tool(wrapped=tool_json, parent=self.tool.parent, gi=self.tool.gi)

    def __init__(self, tool=None, origin='', id='', **kwargs):
        """Initialize the tool widget"""
        self.tool = tool
        self.kwargs = kwargs
        if tool and origin is None: origin = galaxy_url(tool.gi)
        if tool and id is None: id = tool.id
        self.origin = origin

        # Set the right look and error message if tool is None
        if self.tool is None or self.tool.gi is None:
            self.handle_error_task('No Galaxy tool specified.', **kwargs)
            return

        self.load_tool_inputs()
        self.parameter_groups, self.all_params = self.expand_sections()         # List groups and compile all params
        self.function_wrapper = self.create_function_wrapper(self.all_params)   # Build the function wrapper
        self.parameter_spec = self.create_param_spec(kwargs)                    # Create the parameter spec
        self.session_color = session_color(galaxy_url(tool.gi))                 # Set the session color
        self.ui_args = self.create_ui_args(kwargs)                              # Merge kwargs (allows overrides)
        UIBuilder.__init__(self, self.function_wrapper, **self.ui_args)         # Initiate the widget
        self.attach_interactive_callbacks()
        self.attach_help_section()

    def attach_interactive_callbacks(self):
        def dynamic_update_generator(i):
            """Dynamic Parameter Callback"""
            key = self.all_params[i]['py_name']
            def update_form(change):
                value = None
                if not isinstance(change['new'], dict) and (change['new'] or change['new'] == 0): value = change['new']
                if value:
                    if self.all_params[i]['type'] == 'data':
                        if not is_url(value) and not is_id(value): return
                    try: self.dynamic_update({key: value})
                    except ConnectionError as e:
                        self.error = e.body
                        self.busy = False
            return update_form

        def conditional_update_generator(i):
            """Conditional Parameter Callback"""
            conditional_name = self.all_params[i]['py_name']
            def conditional_form(change):
                if change['name'] == 'value' and not isinstance(change['new'], dict) and (change['new'] or change['new'] == 0):
                    self.dynamic_update({ conditional_name: change['new'] }, query_galaxy=False)
            return conditional_form

        def repeat_update_generator(i):
            """Repeat Parameter Callback"""
            repeat_param_name = self.all_params[i]['py_name']
            def repeat_form(change):
                if not isinstance(change['new'], dict):
                    section_count = change['new']
                    self.all_params[i]['value'] = section_count
                    self.dynamic_update({repeat_param_name: section_count})
            return repeat_form

        # Handle conditional parameters
        for i in range(len(self.all_params)):
            if self.all_params[i].get('conditional_test'):
                self.form.form.kwargs_widgets[i].input.observe(conditional_update_generator(i))
                continue

            # Handle dynamic parameters
            if self.all_params[i].get('refresh_on_change', False):
                self.form.form.kwargs_widgets[i].input.observe(dynamic_update_generator(i))
                continue

            # Handle repeat parameters
            if self.all_params[i].get('type') == 'repeat':
                self.form.form.kwargs_widgets[i].input.observe(repeat_update_generator(i))
                continue

    def valid_value(self, name, value):
        values = self.parameter_spec[name].get('choices', {}).values()
        return value in values

    def create_ui_args(self, kwargs):
        ui_args = {  # Assemble keyword arguments
            'color': self.session_color,
            'id': id,
            'logo': GALAXY_LOGO,
            'origin': self.origin,
            'name': self.tool.name,
            'description': self.tool.wrapped['description'],
            'parameters': self.parameter_spec,
            'parameter_groups': self.parameter_groups,
            'subtitle': f'Version {self.tool.version}',
            'upload_callback': self.generate_upload_callback(self.tool.gi, self),
        }
        return {**ui_args, **kwargs, 'parameters': self.parameter_spec}

    def expand_sections(self, input=None):
        # Ensure everything is in the expected format
        if not self.tool or not self.tool.wrapped or 'inputs' not in self.tool.wrapped: return [], []
        if input is None:
            top_level = True
            input = self.tool.wrapped
        else: top_level = False
        if not input.get('inputs'): input['inputs'] = []

        # Assemble the group object and empty parameters
        group = {
            'name': input.get('label', input.get('title', input.get('name', ''))),
            'description': input.get('description', ''),
            'hidden': not input.get('expanded', True),
            'parameters': []
        }
        all_params = []

        for p in input.get('inputs'):
            if p['type'] == 'section':
                p['galaxy_name'] = f"{p['name']}" if top_level or not input.get('galaxy_name') else f"{input['galaxy_name']}|{p['name']}"
                p['py_name'] = python_safe(p['galaxy_name'])

                section_group, section_params = self.expand_sections(p)
                group['parameters'].append(section_group)       # Add param to group structure
                all_params.extend(section_params)               # Add param to the flat list

            elif p['type'] == 'conditional':
                # Add galaxy and python names to conditional (used in full path names)
                p['galaxy_name'] = f"{p['name']}" if top_level or not input.get('galaxy_name') else f"{input['galaxy_name']}|{p['name']}"
                p['py_name'] = python_safe(p['galaxy_name'])

                # Base group object - conditional_params will always be blank at this point
                conditional_group, conditional_params = self.expand_sections(p)

                # Rename the group based on the test parameter's name - conditional params never have a nice label
                conditional_group['name'] = p['test_param'].get('label', p['test_param'].get('title', p['test_param'].get('name', '')))
                if not conditional_group['name']: conditional_group['name'] = p['test_param'].get('name', 'Select')

                # Add the test param and add conditional_test flag
                p['test_param']['galaxy_name'] = f"{p['name']}|{p['test_param']['name']}" if top_level else f"{p['galaxy_name']}|{p['test_param']['name']}"
                p['test_param']['py_name'] = python_safe(p['test_param']['galaxy_name'])
                p['test_param']['conditional_test'] = True
                conditional_group['parameters'].append(p['test_param'].get('py_name', p['test_param']['name']))
                conditional_params.append(p['test_param'])

                # If the test param value is overridden, set new value
                if hasattr(self, 'initial_spec'):
                    if p['test_param']['py_name'] in self.initial_spec:
                        p['test_param']['value'] = self.initial_spec[p['test_param']['py_name']]

                # Add the case params
                for case in p['cases']:
                    case['galaxy_name'] = p['galaxy_name']
                    case['py_name'] = p['py_name']

                    if case['value'] == p['test_param']['value']:
                        for cp in case['inputs']:
                            cp['galaxy_name'] = f"{p['name']}|{cp['name']}" if top_level else f"{p['galaxy_name']}|{cp['name']}"
                            cp['py_name'] = python_safe(cp['galaxy_name'] + '_' + case['value'])
                            cp['conditional_display'] = case['value']           # Save display/submit conditions
                            cp['conditional_param'] = p['test_param']['name']   # Save name of test param
                            cp['hidden'] = False if case['value'] == p['test_param']['value'] else True
                        case_group, case_params = self.expand_sections(case)
                        conditional_group['parameters'].extend(case_group['parameters'])
                        conditional_params.extend(case_params)

                group['parameters'].append(conditional_group)   # Add param to group structure
                all_params.extend(conditional_params)           # Add param to the flat list
            elif p['type'] == 'repeat':
                # Add number parameter for repeat sections
                if 'title' in p and 'label' not in p: p['label'] = f"Number of {p['title']}"
                p['galaxy_name'] = f"{p['name']}" if top_level or not input.get('galaxy_name') else f"{input['galaxy_name']}|{p['name']}"
                p['py_name'] = python_safe(p['galaxy_name'])
                group['parameters'].append(p.get('py_name', p['name']))
                all_params.append(p)
                if 'inputs' not in p: continue

                # Merge repeat values, if overridden
                if hasattr(self, 'initial_spec'):
                    if p['py_name'] in self.initial_spec: p['value'] = int(self.initial_spec[p['py_name']])

                # Add group N times, where N is the number of repeats
                for i in range(p.get('value', p['default'])):
                    p_repeat = deepcopy(p)
                    p_repeat['galaxy_name'] = f"{p['name']}_{i}" if top_level or not input.get('galaxy_name') else f"{input['galaxy_name']}|{p['name']}_{i}"
                    p_repeat['py_name'] = python_safe(p['galaxy_name'])
                    for rp in p_repeat['inputs']:
                        rp['galaxy_name'] = f"{p['name']}_{i}|{rp['name']}" if top_level else f"{p['galaxy_name']}_{i}|{rp['name']}"
                        rp['py_name'] = python_safe(rp['galaxy_name'])
                    repeat_group, repeat_params = self.expand_sections(p_repeat)

                    # Save cached values for repeated sections
                    if 'cache' in p and len(p['cache']) > i:
                        for j in range(len(repeat_params)):
                            if len(p['cache'][i]) > j:
                                if 'value' in p['cache'][i][j]:
                                    repeat_params[j]['value'] = p['cache'][i][j]['value']

                    group['parameters'].append(repeat_group)            # Add param to group structure
                    all_params.extend(repeat_params)                    # Add param to the flat list

            else:
                if not p.get('galaxy_name'):
                    p['galaxy_name'] = f"{p['name']}" if top_level else \
                        (f"{input['galaxy_name']}|{p['name']}" if input.get('galaxy_name') else f"{p['name']}")
                if not p.get('py_name'): p['py_name'] = python_safe(p['galaxy_name'])
                group['parameters'].append(p.get('py_name', p['name']))     # Add param name to group structure
                all_params.append(p)                                        # Add param to the flat list

        return group['parameters'] if top_level else group, all_params

    def dynamic_update(self, overrides={}, query_galaxy=True):
        self.form.busy = True

        # Get the form's current values
        values = [p.get_interact_value() for p in self.form.form.kwargs_widgets]
        keys = [p['py_name'] for p in self.all_params]
        initial_spec = {keys[i]: values[i] for i in range(len(keys))}
        initial_spec = {**initial_spec, **overrides}

        self.overrides = overrides
        self.initial_spec = initial_spec

        # Put the dataset values in the expected format
        spec = self.make_job_spec(self.tool, **initial_spec)

        # Update the Galaxy Tool model
        if query_galaxy:
            tool_json = self.tool.gi.gi.tools.build(tool_id=self.tool.id, history_id=current_history(self.tool.gi).id, inputs=spec)
            self.tool = Tool(wrapped=tool_json, parent=self.tool.parent, gi=self.tool.gi)

        # Build the new function wrapper
        self.parameter_groups, self.all_params = self.expand_sections()         # List groups and compile all params
        self.function_wrapper = self.create_function_wrapper(self.all_params)   # Build the function wrapper
        self.parameter_spec = self.create_param_spec(self.kwargs)               # Create the parameter spec
        self.ui_args = self.create_ui_args(self.kwargs)                         # Merge kwargs (allows overrides)

        # Insert the newly generated widgets into the display
        self.form = UIBuilderBase(self.function_wrapper, _parent=self, **self.ui_args)
        self.output = self.form.output
        self.children = [self.form, self.output]

        # Attach the dynamic refresh callbacks to the new form
        self.attach_interactive_callbacks()
        self.form.busy = False

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
                if type(dataset) == str:
                    # Upload the dataset
                    history = current_history(self.session)
                    dataset_json = self.session.gi.tools.put_url(content=dataset, history_id=history.id)
                    dataset = HistoryDatasetAssociation(ds_dict=dataset_json['outputs'][0], container=history, gi=self.session)

                display(GalaxyDatasetWidget(dataset, logo='none', color=session_color(galaxy_url(self.session), secondary_color=True)))
            return upload_data

    def __init__(self, server_name, session):
        NBTool.__init__(self)
        self.origin = server_name
        self.id = 'galahad_upload'
        self.name = 'Upload Data'
        self.description = 'Upload data files to Galaxy server'
        self.load = lambda **kwargs: GalaxyUploadTool.GalaxyUploadWidget(self, session)
