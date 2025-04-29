import click
from flask.cli import with_appcontext
from . import db
from .models import Column, Backlog

@click.command('seed-db')
@with_appcontext
def seed_db_command():
    """Adiciona dados iniciais ao banco, como colunas padrão."""
    default_columns = [
        {'name': 'A Fazer', 'position': 0},
        {'name': 'Em Andamento', 'position': 1},
        {'name': 'Revisão', 'position': 2},
        {'name': 'Concluído', 'position': 3}
    ]

    existing_columns = Column.query.all()
    if not existing_columns:
        click.echo('Criando colunas padrão...')
        for col_data in default_columns:
            col = Column(name=col_data['name'], position=col_data['position'])
            db.session.add(col)
        db.session.commit()
        click.echo('Colunas padrão criadas com sucesso.')
    else:
        click.echo('Colunas já existem. Nenhuma coluna inicial adicionada.')

    # Cria um backlog padrão se nenhum existir
    default_project_id = 'default_project'
    existing_backlog = Backlog.query.filter_by(project_id=default_project_id).first()
    if not existing_backlog:
        click.echo(f'Criando backlog padrão para o projeto {default_project_id}...')
        default_backlog = Backlog(project_id=default_project_id, name='Backlog Padrão')
        db.session.add(default_backlog)
        db.session.commit()
        click.echo('Backlog padrão criado com sucesso.')
    else:
        click.echo('Backlog padrão já existe.')

def register_commands(app):
    app.cli.add_command(seed_db_command) 