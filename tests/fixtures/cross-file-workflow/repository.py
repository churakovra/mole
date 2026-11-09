from sqlalchemy.orm import Session

class Store:
    def save(self, session: Session):
        try:
            self.validate()
            session.add({'order': 'fixture'})
            session.commit()
            return {'status': 'stored'}
        except ValueError:
            session.rollback()
            raise

    def validate(self):
        return True
