from models import Session, Business


def get_all_businesses():
    session = Session()
    try:
        data = session.query(Business).all()
        return data
    finally:
        session.close()


def add_business(name, fb_page_id):
    session = Session()
    try:
        new_business = Business(name=name, fb_page_id=fb_page_id)
        session.add(new_business)
        session.commit()
        print(f"Added business: {new_business.name}")
        return new_business
    except Exception as e:
        session.rollback()
        print(f"Error adding business: {e}")
        return None
    finally:
        session.close()
