Installation
############
Currently, you need to manually install from Coba's git repository.

First clone the repository::

    $ git clone https://github.com/torfuspolymorphus/coba.git

Then create a virtual environment and activate it::

    $ cd coba
    $ virtualenv venv
    $ source venv/bin/activate

Install all necessary packages::

    $ pip install -r requirements.txt

Finally install Coba itself (note the ``.`` at the end)::

    $ pip install --editable .

At this point you should be able to use the coba command::

    $ coba --help

Coba is now installed in the virtual environment and only available
when that virtual environment is activated. See the `documentation
of virtualenv <https://virtualenv.pypa.io>`_ for more information on
virtual environments.
