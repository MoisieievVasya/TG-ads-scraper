from sqlalchemy import Column, Integer, String, Boolean, Date, ForeignKey, create_engine
from sqlalchemy.orm import relationship, sessionmaker, declarative_base

from config import POSTGRESQl_LINK

Base = declarative_base()

class Business(Base):
    __tablename__ = 'businesses'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    fb_page_id = Column(String, unique=True)

class AdCreative(Base):
    __tablename__ = 'ad_creatives'
    id = Column(Integer, primary_key=True)
    fb_ad_id = Column(String, unique=True)
    business_id = Column(Integer, ForeignKey('businesses.id'))
    image_url = Column(String)
    local_path = Column(String)
    image_hash = Column(String, index=True, nullable=True)
    similar_ads_count = Column(Integer, default=0, index=True)
    start_date = Column(Date)
    end_date = Column(Date, nullable=True)
    duration_days = Column(Integer, default=1)
    is_active = Column(Boolean)
    last_seen = Column(Date)


    business = relationship('Business')


DATABASE_URL = POSTGRESQl_LINK

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
