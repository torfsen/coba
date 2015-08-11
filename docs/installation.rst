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

.. _pygpgme_installation:

.. note::

    The command above will also try to install PyGPGME_, which Coba requires
    for encryption and decryption. Installing PyGPGME from PyPI_ (via ``pip``)
    requires that the header files for libgpgme_ are available. On Ubuntu you
    can install the latter via

    ::

        sudo apt-get install libgpgme11-dev

    Alternatively, you can also install PyGPGME via ``apt-get`` instead of
    ``pip``::

        sudo apt-get install python-gpgme

    Note, however, that this will install PyGPGME globally and not just into
    Coba's virtual environment. This means that you also need to `make site
    site packages available in your virtual environment
    <https://stackoverflow.com/q/3371136/857390>`_.

    Finally, you can also choose to not install PyGPGME at all -- in that case
    encryption and decryption will not be available.

.. _PyGPGME: https://pypi.python.org/pypi/pygpgme
.. _PyPI: https://pypi.python.org
.. _libgpgme: https://www.gnupg.org/%28it%29/related_software/gpgme/

Finally install Coba itself (note the ``.`` at the end)::

    $ pip install --editable .

At this point you should be able to use the coba command::

    $ coba --help

Coba is now installed in the virtual environment and only available
when that virtual environment is activated. See the `documentation
of virtualenv <https://virtualenv.pypa.io>`_ for more information on
virtual environments.
