from app import db, User, Procedimento, importar_procedimentos_base
from flask import Flask
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SUPABASE_DB_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

def import_for_users():
    with app.app_context():
        # Buscar usuários
        user1 = User.query.filter_by(email='growth.andre@gmail.com').first()
        user2 = User.query.filter_by(email='sharkplayer.br@gmail.com').first()

        if user1:
            print(f"Importando procedimentos para {user1.email}")
            importar_procedimentos_base(user1.id)
        else:
            print("Usuário growth.andre@gmail.com não encontrado")

        if user2:
            print(f"Importando procedimentos para {user2.email}")
            importar_procedimentos_base(user2.id)
        else:
            print("Usuário sharkplayer.br@gmail.com não encontrado")

if __name__ == '__main__':
    import_for_users()
