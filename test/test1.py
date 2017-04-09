from skiff import Skiff, make_response

app = Skiff()


@app.route('/')
def index():
    content = 'Hello World!'
    return content


@app.route('/<corp>/<int:user>')
def say_hello(corp, user):
    content = 'Hello, user #{} from {}.'.format(user, corp)
    response = make_response(content)
    return response


@app.error_handler(500)
def internal_error(e):
    content = 'This is an error handler.'
    return content


app.run(port=8080)

