from app import create_app
import logging

# Cria a aplicação
app = create_app()

if __name__ == '__main__':
    print("\n=== Rotas Registradas ===")
    print("\nBlueprints:")
    for name, blueprint in app.blueprints.items():
        print(f"- {name}: {blueprint.url_prefix}")
    
    print("\nRotas:")
    for rule in app.url_map.iter_rules():
        print(f"- {rule.endpoint}: {rule}")
    
    print("\nIniciando servidor...")
    app.run(debug=True, port=5000)
