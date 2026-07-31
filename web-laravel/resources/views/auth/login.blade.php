<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Staff sign in</title>
    <style>
        * { box-sizing: border-box; }
        body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f3f5f7; color: #18212b; font-family: Arial, sans-serif; }
        main { width: min(420px, calc(100% - 32px)); background: #fff; border: 1px solid #d8dee5; padding: 28px; }
        h1 { margin: 0 0 8px; font-size: 24px; }
        p { margin: 0 0 24px; color: #53606d; }
        label { display: block; margin: 16px 0 6px; font-weight: 700; }
        input { width: 100%; min-height: 44px; padding: 10px 12px; border: 1px solid #aeb8c2; font: inherit; }
        input:focus { outline: 3px solid #b8d8f5; border-color: #28689c; }
        button { width: 100%; min-height: 44px; margin-top: 22px; border: 0; background: #1f5e87; color: #fff; font: inherit; font-weight: 700; cursor: pointer; }
        .errors { margin: 0 0 16px; padding: 12px; border-left: 4px solid #b42318; background: #fff1f0; color: #7a271a; }
    </style>
</head>
<body>
<main>
    <h1>Staff sign in</h1>
    <p>Use your authorized internal account.</p>

    @if ($errors->any())
        <div class="errors" role="alert">
            @foreach ($errors->all() as $error)
                <div>{{ $error }}</div>
            @endforeach
        </div>
    @endif

    <form method="POST" action="{{ route('login.store') }}">
        @csrf
        <label for="email">Email</label>
        <input id="email" name="email" type="email" value="{{ old('email') }}" autocomplete="username" required autofocus>

        <label for="password">Password</label>
        <input id="password" name="password" type="password" autocomplete="current-password" required>

        <button type="submit">Sign in</button>
    </form>
</main>
</body>
</html>
