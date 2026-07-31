# Composer Blocker

Current environment checks:

```text
composer --version => command not found
php --version => command not found
```

Because PHP and Composer are missing, this session did not run Laravel project generation and did not create fake generated Laravel files such as `artisan`, framework bootstrap files, `composer.lock`, or `vendor/`.

The files in this directory are W0-W2 skeletons and documentation only. A PHP/Composer-ready environment is required before running:

```text
composer create-project laravel/laravel web-laravel
php artisan migrate
php artisan test
```
