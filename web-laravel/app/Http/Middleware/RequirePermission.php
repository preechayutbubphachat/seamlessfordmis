<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

final class RequirePermission
{
    public function handle(Request $request, Closure $next, ?string $permission = null): Response
    {
        $user = $request->user();

        if ($user === null || $permission === null || ! $user->hasPermission($permission)) {
            abort(Response::HTTP_FORBIDDEN, 'This action is not authorized.');
        }

        return $next($request);
    }
}
