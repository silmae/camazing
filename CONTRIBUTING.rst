.. highlight:: shell

.. _Contributing:

============
Contributing
============

Contributions are welcome! 

Report bugs or give feedback at https://github.com/silmae/camazing/issues.

Get Started!
------------

Ready to contribute? Here's how to set up `camazing` for local development.

1. Fork the `camazing` repo on GitHub.
2. Clone your fork locally::

    $ git clone git@github.com:your_name_here/camazing.git

3. Install the package itself using pip, including the documentation build
   dependencies:

    $ pip install -e .[doc]

4. Create a branch for local development::

    $ git checkout -b name-of-your-bugfix-or-feature

   Now you can make your changes locally.

5. Commit your changes and push your branch to GitHub::

    $ git add .
    $ git commit -m "Your detailed description of your changes."
    $ git push origin name-of-your-bugfix-or-feature

   Remember to include a note in CHANGELOG.rst and add relevant
   documentation.

6. Submit a pull request through the GitHub website.

Testing
-------

Since `camazing` is mostly a hardware control library, meaningful automated
testing is not simple to achieve as it requires some form of camera simulation.
You should test any functional changes with your own hardware or an camera
simulator, if you have one available (and reports of working approaches are
appreciated).
