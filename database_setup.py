#
#
# database_setup.py -- to create the database for the Catalog Project
#
# Many thanks to the people at Udacity
# and of course the Full Stack Foundations - Lesson 4 examples

import os
import sys
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy import UniqueConstraint


Base = declarative_base()

# The table name 'user' is populated from the Google or Facebook log ins
# The user id is linked to the category and item tables to determine who
# created those entries and who can subsequently amend.
class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)
    picture = Column(String(250))

# The table name 'category' is the top end of our application.
# One category can have many items linked to it. For example a library category has many books.
# The table is linked to the 'user' table to determine who created the category.
# The table has a one to many relationship with the 'item' table.
class Category(Base):
    __tablename__ = 'category'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False, unique=True)
    picture = Column(String(250))
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'name': self.name,
            'id': self.id,
            'picture': self.picture,
        }

# The table name 'item' is the bottom end of our application.
# One item can only be linked to one category. For example a library book can only be in one library at a time.
# Noting that one category can have many items.
# The table is linked to the 'user' table to determine who created the item.
class Item(Base):
    __tablename__ = 'item'

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    description = Column(String(250))
    picture = Column(String(250))
    category_id = Column(Integer, ForeignKey('category.id'))
    category = relationship(Category)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'name': self.name,
            'description': self.description,
            'id': self.id,
            'picture': self.picture,
        }

print "Database setup has completed"

engine = create_engine('sqlite:///catalog.db')


Base.metadata.create_all(engine)
