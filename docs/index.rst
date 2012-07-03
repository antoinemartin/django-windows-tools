.. django-windows-tools documentation master file, created by
   sphinx-quickstart on Tue Jul 03 18:56:34 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to django-windows-tools
===============================

django-windows-tools is a small Django application providing management 
commands to help hosting Django projects in a Windows environment.

This project started when a Django project that started as a temporary
proof of concept running on a Linux box became something that needed to 
go to production in a IIS/SQL Server environment.

We faced three concerns:

- Database access.
- Running a Django application behind IIS.
- Running Django background processes (Celery, Celery Beat)

The database is a no brainer with the help of `django-mssql`_ and pywin32
as it allowed an allmost seamless switch between MySQL and SQL Server. 

For Hosting the Django project behind IIS, things became harder. There are
several solutions around (such as the one from `HeliconTech`_), but they are
either unmaintained, convoluted or Closed Source. We came out with
a solution that needs only Open Source software and that can easily be automated.

Last, for background and scheduled task, one wants to use celery and 
its beat scheduler. Again, we came out with a solution allowing to run 
the Django Background processes in a Windows Service.

django-windows-tools packages the solutions we found 
and provides Django management commands that ease the deployment and configuration
of a Django project on Windows.

.. _django-mssql: https://bitbucket.org/Manfre/django-mssql/src
.. _HeliconTech: http://www.helicontech.com/articles/running-django-on-windows-with-performance-tests/

Documentation
-------------

.. toctree::
   :maxdepth: 2

   quickstart


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

