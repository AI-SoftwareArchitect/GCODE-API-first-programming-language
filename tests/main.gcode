api start {
    route "/" GET {
        return "<html><body><h1>Hoşgeldiniz!</h1><p>Login olabilirsiniz.</p><a href=\"/login\">Login Ol</a></body></html>";
    }

    route "/login" GET {
        return """
<html>
<head>
    <title>Login</title>
</head>
<body style="display:flex;justify-content:center;align-items:center;height:100vh;">
    <form method="POST" action="/login" style="text-align:center;">
        <h2>Login Formu</h2>
        <input name="username" placeholder="Kullanıcı Adı" /><br/><br/>
        <input name="password" type="password" placeholder="Şifre" /><br/><br/>
        <button type="submit">Giriş</button>
    </form>
</body>
</html>
""";
    }
}