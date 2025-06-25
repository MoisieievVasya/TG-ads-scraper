import shutil
import asyncio
from pathlib import Path
from sqlalchemy.orm import Session
from database.models import Session as DBSession, AdCreative

async def clean_database():
    session: Session = DBSession()
    try:
        session.query(AdCreative).delete()
        session.commit()
        print("Data Base cleaned")
    except Exception as e:
        session.rollback()
        print(f"Cleanup failed {e}")
    finally:
        session.close()

async def clean_images_folder():
    images_path = Path("images")
    if images_path.exists() and images_path.is_dir():
        for item in images_path.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception as e:
                print(f"Can't clean up {item}: {e}")
        print("Folder cleanup successful")
    else:
        print("Folder images doesn't exist")

async def cleanup():
    await clean_database()
    await clean_images_folder()

async def run_clean_up():
    while True:
        print("Start cleanup")
        try:
            asyncio.create_task(cleanup())
            print("Cleanup completed")
        except Exception as e:
            print(f"Cleanup failed due {e}")

        await asyncio.sleep(86400)



if __name__ == "__main__":
    clean_database()
    clean_images_folder()