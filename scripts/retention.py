"""Run daily. Deletes live predictions after 90 days, expired sessions and IP pseudonyms."""
import time
from sqlalchemy import delete
from app.config import Settings
from app.db import Prediction,Session,Limit,database
def main():
    settings=Settings.load();engine,db=database(settings.database_url);now=int(time.time())
    with db() as s:
        s.execute(delete(Prediction).where(Prediction.created<now-90*86400))
        s.execute(delete(Session).where(Session.expires<now))
        s.execute(delete(Limit).where(Limit.expires<now));s.commit()
    engine.dispose();print('Retention task completed; no user data included in output.')
if __name__=='__main__':main()
