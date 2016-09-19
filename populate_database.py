# A file to populate the tables in the database 'catalog'.
# 
#
# Many thanks to the people at Udacity and of course the Full Stack Foundations - Lesson 4 examples

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import Category, Base, Item, User

engine = create_engine('sqlite:///catalog.db')
# Bind the engine to the metadata of the Base class so that the
# declaratives can be accessed through a DBSession instance
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)

session = DBSession()

user1 = User(name="Andrew Gardiner", email="deputy2426@gmail.com",
             picture='https://en.wikipedia.org/wiki/Savannah_Sand_Gnats#/media/File:Gnats_cap.PNG')
session.add(user1)
session.commit()

# Category Soccer with Items
category1 = Category(user_id=1,name="Soccer", picture ='')

session.add(category1)
session.commit()

item1 = Item(user_id=1, name="Boots", description="Useful things to kick the ball with.",
                     category=category1, picture = "")

session.add(item1)
session.commit()


item2 = Item(user_id=1, name="Real Madrid Jersey", description="Fully signed Ronaldo kit",
                     category=category1, picture = "")

session.add(item2)
session.commit()

item3 = Item(user_id=1,name="Manchester United Ground", description="The field of dreams",
                     category=category1, picture = "")

session.add(item3)
session.commit()

# Category AFL with Items
category2 = Category(user_id=1,name="Australian Football", picture = "")

session.add(category2)
session.commit()

item1 = Item(user_id=1,name="Real Footy Boots", description="Useful things to kick the ball with.",
                     category=category2, picture = "")

session.add(item1)
session.commit()


item2 = Item(user_id=1,name="Hawthorn Guernsey", description="A legend team with legend players!",
                     category=category2, picture = "")

session.add(item2)
session.commit()

item3 = Item(user_id=1, name="Melbourne Cricket Ground", description="The field of footy AFL dreams",
                     category=category2, picture = "")

session.add(item3)
session.commit()


print "added menu items!"
Base.metadata.create_all(engine)