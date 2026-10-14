import time
from sqlalchemy import String, Integer, Float, JSON, ForeignKey, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

class Base(DeclarativeBase):pass
class User(Base):
    __tablename__='users'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    email:Mapped[str]=mapped_column(String(254),unique=True)
    password_hash:Mapped[str]=mapped_column(String(255))
class Session(Base):
    __tablename__='sessions'
    token_hash:Mapped[str]=mapped_column(String(64),primary_key=True)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    csrf:Mapped[str]=mapped_column(String(64))
    expires:Mapped[int]=mapped_column(Integer)
class Prediction(Base):
    __tablename__='predictions'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    user_id:Mapped[str]=mapped_column(ForeignKey('users.id',ondelete='CASCADE'),index=True)
    created:Mapped[int]=mapped_column(Integer,default=lambda:int(time.time()))
    features:Mapped[dict]=mapped_column(JSON)
    probability:Mapped[float]=mapped_column(Float)
    band:Mapped[str]=mapped_column(String(30))
    version:Mapped[str]=mapped_column(String(30))
    outcome:Mapped[int|None]=mapped_column(Integer,nullable=True)
    reasons:Mapped[list]=mapped_column(JSON)
class Limit(Base):
    __tablename__='rate_limits'
    key:Mapped[str]=mapped_column(String(64),primary_key=True)
    count:Mapped[int]=mapped_column(Integer)
    expires:Mapped[int]=mapped_column(Integer)

def database(url):
    engine=create_engine(url,pool_pre_ping=True,**({'connect_args':{'check_same_thread':False}} if url.startswith('sqlite') else {}))
    if url.startswith('sqlite'):
        @event.listens_for(engine,'connect')
        def foreign_keys(connection,record):connection.execute('PRAGMA foreign_keys=ON')
    return engine,sessionmaker(engine,expire_on_commit=False)
