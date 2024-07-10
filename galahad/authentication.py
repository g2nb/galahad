from collections import OrderedDict
from packaging.version import Version, InvalidVersion
from bioblend.galaxy.objects import GalaxyInstance
from nbtools import UIBuilder, ToolManager, NBTool, EventManager, DataManager, Data
from IPython.display import display
from .dataset import GalaxyDatasetWidget
from .history import GalaxyHistoryWidget
from .sessions import session
from .tool import GalaxyTool, GalaxyUploadTool
from .utils import GALAXY_LOGO, GALAXY_SERVERS, server_name, session_color, galaxy_url, data_icon, poll_data_and_update, \
    skip_tool, data_name, strip_version

REGISTER_EVENT = """
    const target = event.target;
    const widget = target.closest('.nbtools') || target;
    const server_input = widget.querySelector('input[type=text]');
    if (server_input) window.open(server_input.value + '/login/start');
    else console.warn('Cannot obtain Galaxy Server URL');"""


class GalaxyAuthWidget(UIBuilder):
    """A widget for authenticating with a Galaxy server"""
    login_spec = {  # The display values for building the login UI
        'name': 'Login',
        'collapse': False,
        'display_header': False,
        'logo': GALAXY_LOGO,
        'color': session_color(),
        'run_label': 'Log into Galaxy',
        'buttons': {
            'Register an Account': REGISTER_EVENT
        },
        'parameters': {
            'server': {
                'name': 'Galaxy Server',
                'type': 'choice',
                'combo': True,
                'sendto': False,
                'default': GALAXY_SERVERS['Galaxy Main'],
                'choices': GALAXY_SERVERS
            },
            'email': {
                'name': 'Email',
                'sendto': False,
            },
            'password': {
                'name': 'Password',
                'type': 'password',
                'sendto': False,
            }
        }
    }

    def __init__(self, session=None, **kwargs):
        """Initialize the authentication widget"""
        self.session = session if isinstance(session, GalaxyInstance) else None

        # Apply the display spec
        for key, value in self.login_spec.items(): kwargs[key] = value

        # If a session has been provided, login automatically
        if session:
            for k, v in [('collapsed', True), ('name', self.session.email), ('subtitle', galaxy_url(self.session)),
                         ('display_header', False), ('display_footer', False)]: kwargs[k] = v
            self.prepare_session()

        # Call the superclass constructor with the spec
        UIBuilder.__init__(self, self.login, **kwargs)

    def login(self, server, email, password):
        """Login to the Galaxy server"""
        try:
            self.session = GalaxyInstance(url=server, email=email, password=password)
        except Exception:
            self.error = 'Invalid email address or password. Please try again.'
            return
        self.replace_widget()
        self.prepare_session()

    def replace_widget(self):
        """Replace the unauthenticated widget with the authenticated mode"""
        self.form.form.children[2].value = ''        # Blank password so it doesn't get serialized

        def refresh_history(history):
            self.register_history()
            EventManager.instance().dispatch("galaxy.history_refresh", self.session)

        history_widget = UIBuilder(refresh_history, name=self.session.gi.email, subtitle=galaxy_url(self.session),
            display_header=False, logo=GALAXY_LOGO, color=session_color(galaxy_url(self.session)), collapse=False,
            run_label='Refresh History', busy=True, info='Signing in to Galaxy',
            parameters={
                'history': {
                    'label': 'History',
                    'type': 'choice',
                    'description': 'Select a Galaxy history to use',
                    'choices': {h.name: h.id for h in self.session.histories.list(deleted=False)},
                    'optional': True
                }
        })
        self.history_widget = history_widget
        display(history_widget)

        def change_history(change):
            # Set the current history
            self.session.current_history = self.session.histories.get(history_widget.form.form.children[0].input.value)

            # Trigger file inputs of tools to update their history lists
            EventManager.instance().dispatch("galaxy.history_refresh", self.session)

        history_widget.form.form.children[0].input.observe(change_history)
        self.form.close()

    def prepare_session(self):
        """Prepare a valid session by registering the session and tools"""
        self.register_session()     # Register the session with the SessionList
        self.register_tools()       # Register the modules with the ToolManager
        self.register_history()     # Add history to the data panel
        self.trigger_login()        # Trigger login callbacks of job and tool widgets

    def register_session(self):
        """Register the validated credentials with the SessionList"""
        self.history_widget.info = 'Registering session'
        session.register(self.session)

    def register_tools(self):
        """Get the list available tools and register widgets for them with the tool manager"""
        server = server_name(galaxy_url(self.session))
        safe_tools = self.safe_tools()
        tools = [GalaxyTool(server, galaxy_tool) for galaxy_tool in safe_tools]
        tools.append(GalaxyUploadTool(server, self.session))
        self.history_widget.info = 'Registering tools'
        ToolManager.instance().register_all(tools)

    def safe_tools(self):
        self.history_widget.info = 'Querying Galaxy for list of tools'
        raw_list = self.session.tools.list()
        safe_list = OrderedDict()
        for galaxy_tool in raw_list:
            if skip_tool(galaxy_tool): continue
            base_id = strip_version(galaxy_tool.id)
            if GalaxyAuthWidget.later_version(safe_list.get(base_id), galaxy_tool):
                safe_list[base_id] = galaxy_tool
        return list(safe_list.values())

    @staticmethod
    def later_version(tool_a, tool_b):
        """Returns true if tool_b has a later version number than tool_a"""
        # Handle the None cases
        if tool_a is None: return True
        if tool_b is None: return False

        # Parse versions to make sure they work
        try: version_b = Version(tool_b.version)
        except InvalidVersion: return False
        try: version_a = Version(tool_a.version)
        except InvalidVersion: return True

        return version_a <= version_b

    def register_history(self):
        data_list = []
        origin = server_name(galaxy_url(self.session))
        def create_history_lambda(history): return lambda: GalaxyHistoryWidget(history)
        def create_dataset_lambda(id): return lambda: GalaxyDatasetWidget(id)

        self.history_widget.info = 'Querying Galaxy for histories'
        for history in self.session.histories.list():
            # Register a custom data group widget (GalaxyHistoryWidget) with the manager
            DataManager.instance().group_widget(origin=origin, group=history.name, widget=create_history_lambda(history))

            # Add data entries for all output files
            for content in history.content_infos:
                if content.wrapped['deleted']: continue
                kind = 'error' if content.state == 'error' else (content.wrapped['extension'] if 'extension' in content.wrapped else '')
                data = Data(origin=origin, group=history.name, uri=content.id, label=data_name(content), kind=kind, icon=data_icon(content.state))
                DataManager.instance().data_widget(origin=data.origin, uri=data.uri, widget=create_dataset_lambda(content.id))
                data_list.append(data)
                poll_data_and_update(content)
        self.history_widget.info = 'Registering history contents'
        DataManager.instance().register_all(data_list)

    def trigger_login(self):
        """Dispatch a login event after authentication"""
        self.history_widget.info = 'Loading tool widgets embedded in the notebook'
        EventManager.instance().dispatch("galaxy.login", self.session)
        self.history_widget.info = 'Finalizing session'
        EventManager.instance().dispatch("nbtools.refresh_data", None)
        self.history_widget.info = ''
        self.history_widget.busy = False


class AuthenticationTool(NBTool):
    """Tool wrapper for the authentication widget"""
    origin = '+'
    id = 'galahad_authentication'
    name = 'Galaxy Login'
    description = 'Log into a Galaxy server'
    load = lambda x: GalaxyAuthWidget()


# Register the authentication widget
ToolManager.instance().register(AuthenticationTool())

