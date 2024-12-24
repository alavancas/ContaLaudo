from app import app, db, User, Instituicao, Periodo, Laudo
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def init_db():
    with app.app_context():
        # Criar todas as tabelas
        db.drop_all()
        db.create_all()
        
        # Criar usuário de teste
        test_user = User(
            username='test',
            password_hash=generate_password_hash('test', method='pbkdf2:sha256')
        )
        db.session.add(test_user)
        
        # Criar algumas instituições de teste
        inst1 = Instituicao(
            nome='Hospital A',
            data_criacao=datetime.now()
        )
        inst2 = Instituicao(
            nome='Hospital B',
            data_criacao=datetime.now()
        )
        db.session.add(inst1)
        db.session.add(inst2)
        
        db.session.commit()  # Commit para gerar os IDs
        
        # Data atual e primeiro dia do mês
        hoje = datetime.now()
        primeiro_dia_mes = hoje.replace(day=1)
        ultimo_dia_mes = (primeiro_dia_mes + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        # Criar alguns períodos de teste
        periodo1 = Periodo(
            user_id=test_user.id,
            instituicao_id=inst1.id,
            data_criacao=datetime.now(),
            data_inicio=primeiro_dia_mes,
            data_fim=ultimo_dia_mes,
            tipo_remuneracao='fixo',
            valor_fixo=5000.0
        )
        periodo2 = Periodo(
            user_id=test_user.id,
            instituicao_id=inst2.id,
            data_criacao=datetime.now(),
            data_inicio=primeiro_dia_mes,
            data_fim=ultimo_dia_mes,
            tipo_remuneracao='producao',
            valor_fixo=None
        )
        db.session.add(periodo1)
        db.session.add(periodo2)
        
        # Commit das mudanças
        db.session.commit()
        print('Banco de dados inicializado com sucesso!')

if __name__ == '__main__':
    init_db()
