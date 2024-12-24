from app import app, db, User

def create_initial_user():
    with app.app_context():
        # Verificar se já existe algum usuário
        if User.query.first() is None:
            # Criar um novo usuário
            user = User(username='admin')
            user.set_password('admin123')
            
            db.session.add(user)
            db.session.commit()
            print('Usuário criado com sucesso!')
            print('Username: admin')
            print('Senha: admin123')
        else:
            print('Já existe um usuário no sistema.')
