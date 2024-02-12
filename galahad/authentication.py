from bioblend.galaxy.objects import GalaxyInstance
from nbtools import UIBuilder, ToolManager, NBTool, EventManager, DataManager, Data
from .history import GalaxyHistoryWidget
from .sessions import session
from .tool import GalaxyTool
from .utils import GALAXY_LOGO, GALAXY_SERVERS, server_name, session_color, galaxy_url

REGISTER_EVENT = """
    const target = event.target;
    const widget = target.closest('.nbtools') || target;
    const server_input = widget.querySelector('input[type=text]');
    if (server_input) window.open(server_input.value + '/login/start');
    else console.warn('Cannot obtain Galaxy Server URL');"""


class GalaxyAuthWidget(UIBuilder):
    """A widget for authenticating with a GenePattern server"""
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
        self.replace_widget()
        self.prepare_session()

    def replace_widget(self):
        """Replace the unauthenticated widget with the authenticated mode"""
        self.form.form.children[2].value = ''        # Blank password so it doesn't get serialized
        self.form.collapsed = True
        self.form.name = self.session.gi.email
        self.form.subtitle = galaxy_url(self.session)
        self.form.display_header=False
        self.form.display_footer=False
        self.form.form.children = []

    def prepare_session(self):
        """Prepare a valid session by registering the session and tools"""
        self.register_session()     # Register the session with the SessionList
        self.register_tools()       # Register the modules with the ToolManager
        self.register_history()     # Add history to the data panel
        self.trigger_login()        # Trigger login callbacks of job and tool widgets

    def register_session(self):
        """Register the validated credentials with the SessionList"""
        session.register(self.session)

    def register_tools(self):
        """Get the list available tools and register widgets for them with the tool manager"""
        server = server_name(galaxy_url(self.session))
        tools = [GalaxyTool(server, galaxy_tool) for galaxy_tool in self.session.tools.list()]
        ToolManager.instance().register_all(tools)

    def register_history(self):
        data_list = []
        origin = server_name(galaxy_url(self.session))
        for history in self.session.histories.list():
            # Register a custom data group widget (GalaxyHistoryWidget) with the manager
            DataManager.instance().group_widget(origin=origin, group=history.name, widget=GalaxyHistoryWidget(history))

            # Add data entries for all output files
            for content in history.content_infos:
                if content.wrapped['deleted']: continue
                kind = content.wrapped['extension'] if 'extension' in content.wrapped else ''
                data_list.append(Data(origin=origin, group=history.name,
                                      uri=f"data://{content.id}",
                                      label=content.name, kind=kind))
        DataManager.instance().register_all(data_list)

    def trigger_login(self):
        """Dispatch a login event after authentication"""
        self.info = "Successfully logged into Galaxy"
        EventManager.instance().dispatch("galaxy.login", self.session)


class AuthenticationTool(NBTool):
    """Tool wrapper for the authentication widget"""
    origin = '+'
    id = 'galaxy_authentication'
    name = 'Galaxy Login'
    description = 'Log into a Galaxy server'
    load = lambda x: GalaxyAuthWidget()


# Register the authentication widget
ToolManager.instance().register(AuthenticationTool())

