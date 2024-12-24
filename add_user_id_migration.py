from app import db, app
from sqlalchemy import text

def add_user_id_column():
    with app.app_context():
        try:
            # Adiciona a coluna user_id
            db.session.execute(text('ALTER TABLE procedimento ADD COLUMN user_id INTEGER REFERENCES "user" (id)'))
            db.session.commit()
            print("Coluna user_id adicionada com sucesso!")
        except Exception as e:
            print(f"Erro ao adicionar coluna: {str(e)}")
            db.session.rollback()

if __name__ == '__main__':
    add_user_id_column()
