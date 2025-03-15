from app import create_app, socketio

app = create_app()

if __name__ == '__main__':
    # Simple Flask run without specifying SocketIO options
    socketio.run(app, debug=app.config.get('DEBUG', False))
