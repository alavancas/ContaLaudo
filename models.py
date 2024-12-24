from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    periodos = db.relationship('Periodo', backref='user', lazy=True)

class Instituicao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    periodos = db.relationship('Periodo', backref='instituicao', lazy=True)

class Periodo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    tipo_remuneracao = db.Column(db.String(20), nullable=False)  # fixo, producao, fixo_producao, pontuacao
    valor_fixo = db.Column(db.Float, nullable=True)
    instituicao_id = db.Column(db.Integer, db.ForeignKey('instituicao.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    laudos = db.relationship('Laudo', backref='periodo', lazy=True)

class Laudo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, nullable=False)
    tipo_laudo = db.Column(db.String(50), nullable=False)  # raio_x, tomografia, ressonancia, etc
    valor = db.Column(db.Float, nullable=False)
    comentarios = db.Column(db.Text, nullable=True)
    periodo_id = db.Column(db.Integer, db.ForeignKey('periodo.id'), nullable=False)
