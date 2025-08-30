from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from .session import Base


class Filter(Base):
    __tablename__ = "filters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    model = Column(String, nullable=False)
    max_price = Column(Integer, nullable=True)
    last_page = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    ads = relationship("FilterAd", back_populates="filter", cascade="all, delete-orphan")


class Ad(Base):
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, index=True)
    lalafo_id = Column(String, unique=True, nullable=False)
    title = Column(String)
    city = Column(String)
    url = Column(String)
    last_price = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    filters = relationship("FilterAd", back_populates="ad", cascade="all, delete-orphan")


class FilterAd(Base):
    __tablename__ = "filter_ads"

    id = Column(Integer, primary_key=True, index=True)
    filter_id = Column(Integer, ForeignKey("filters.id", ondelete="CASCADE"))
    ad_id = Column(Integer, ForeignKey("ads.id", ondelete="CASCADE"))
    seen_price = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    filter = relationship("Filter", back_populates="ads")
    ad = relationship("Ad", back_populates="filters")

    __table_args__ = (UniqueConstraint("filter_id", "ad_id", name="uq_filter_ad"),)

