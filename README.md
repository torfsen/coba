Coba - a continuous backup system
=================================
Coba backs up your files whenever you change them, so you don't have to
remember to do backups anymore and never again loose data because your
backups are too old.

**Coba is in early development and by no means ready for use as your
primary backup system. It will probably corrupt your data, break your
heart and eat your homework. You have been warned.**


Development
-----------
First clone the Coba repository:

    $ git clone https://github.com/torfuspolymorphus/coba.git

Then create a virtual env and activate it:

    $ cd coba
    $ virtualenv venv
    $ source venv/bin/activate

Install all packages that are necessary for development:

    $ pip install -r requirements.txt

Also install Coba itself as an editable package, which creates the `coba`
command line executable thanks to Click's
[setuptools integration](http://click.pocoo.org/4/setuptools/):

    $ pip install --editable .

At this point you should be able to use the `coba` command:

    $ coba --help

Now that your environment is set up you should run the tests:

    $ ./runtests.py

Make sure to [create an issue](https://github.com/torfuspolymorphus/coba/issues)
if any of the tests fail.


License
-------
Coba is distributed under the MIT license. See the file `LICENSE` for details.

