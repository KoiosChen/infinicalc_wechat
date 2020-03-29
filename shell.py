#!/usr/bin/env python
import os
from app import create_app, db
from app.models import Users, Roles, PATH_PREFIX, Permissions, user_role, role_menu, Menu
from flask_script import Manager, Shell
from flask_migrate import Migrate, MigrateCommand

__author__ = 'Koios'

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
manager = Manager(app)
migrate = Migrate(app, db)


def make_shell_context():
    return dict(app=app, db=db, Permissions=Permissions, Users=Users, Roles=Roles, user_role=user_role,
                role_menu=role_menu, Menu=Menu)


manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)

if __name__ == '__main__':
    manager.run()
