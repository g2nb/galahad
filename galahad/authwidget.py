from bioblend.galaxy import GalaxyInstance
from nbtools import UIBuilder, ToolManager, NBTool, EventManager, DataManager, Data
from .sessions import session
from .utils import GALAXY_LOGO, GALAXY_SERVERS, server_name, session_color


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
        self.session = session if session else None

        # TODO: Redo or cut
        # # Assign the session object, lazily creating one if needed
        # if session is None: self.session = GalaxyInstance(url='', email='', password='')
        # else: self.session = session
        #
        # # Set blank token
        # self.token = None
        #
        # # Check to see if the provided session has valid credentials
        # if self.has_credentials() and self.validate_credentials():
        #     self.prepare_session()
        #
        #     # Display the widget with the system message and no form
        #     UIBuilder.__init__(self, lambda: None, name=self.session.username, subtitle=self.session.url,
        #                        display_header=False, display_footer=False, color=session_color(self.session.url),
        #                        collapsed=True, logo=GALAXY_LOGO, **kwargs)
        #
        # # If not, prompt the user to login
        # else:

        # Apply the display spec
        for key, value in self.login_spec.items(): kwargs[key] = value

        # Call the superclass constructor with the spec
        UIBuilder.__init__(self, self.login, **kwargs)

    def login(self, server, email, password):
        """Login to the Galaxy server"""
        try:
            self.session = GalaxyInstance(url=server, email=email, password=password)
            self.replace_widget()
            self.prepare_session()
        except Exception:
            self.error = 'Invalid email address or password. Please try again.'

    def replace_widget(self):
        """Replace the unauthenticated widget with the authenticated mode"""
        self.form.form.children[2].value = ''        # Blank password so it doesn't get serialized
        self.form.collapsed = True
        self.form.name = self.session.email
        self.form.subtitle = self.session.url[:-4]
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
        # TODO: Implement sessionlist

    def register_tools(self):
        """Get the list available tools and register widgets for them with the tool manager"""
        # TODO: Implement for Galaxy
        pass
        # for task in self.session.get_task_list():
        #     tool = TaskTool(server_name(self.session.url), task)
        #     ToolManager.instance().register(tool)

    def register_history(self):
        # TODO: Implement for Galaxy
        pass
        # data_list = []
        # for job in self.session.get_recent_jobs():
        #     origin = server_name(self.session.url)
        #     group = f"{job.job_number}. {job.task_name}"
        #
        #     # Register a custom data group widget (GPJobWidget) with the manager
        #     DataManager.instance().group_widget(origin=origin, group=group, widget=GPJobWidget(job))
        #
        #     # Add data entries for all output files
        #     for file in job.get_output_files():
        #         data_list.append(Data(origin=origin, group=group, uri=file.get_url()))
        # DataManager.instance().register_all(data_list)

    def trigger_login(self):
        """Dispatch a login event after authentication"""
        self.info = "Successfully logged into Galaxy"
        EventManager.instance().dispatch("galaxy.login", self.session)


class AuthenticationTool(NBTool):
    """Tool wrapper for the authentication widget"""
    origin = '+'
    id = 'authentication'
    name = 'Galaxy Login'
    description = 'Log into a Galaxy server'
    load = lambda x: GalaxyAuthWidget()


# Register the authentication widget
ToolManager.instance().register(AuthenticationTool())

