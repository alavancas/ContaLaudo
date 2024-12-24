from app import app, db
from flask_migrate import init, migrate, upgrade

def init_database():
    with app.app_context():
        # Criar as tabelas
        db.create_all()
        
        # Inicializar as migrações
        init()
        migrate()
        upgrade()

if __name__ == '__main__':
    init_database()
    print("Banco de dados inicializado com sucesso!")
