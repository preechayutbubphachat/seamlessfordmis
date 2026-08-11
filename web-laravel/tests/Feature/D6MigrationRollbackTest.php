<?php

namespace Tests\Feature;

use PDO;
use Symfony\Component\Process\Process;
use Tests\TestCase;

final class D6MigrationRollbackTest extends TestCase
{
    /** @var list<string> */
    private array $temporaryDatabases = [];

    public function test_000006_up_and_down_remove_all_d6_review_objects_on_isolated_sqlite(): void
    {
        $database = $this->temporaryDatabase();
        $this->migrateThrough($database, '2026_08_07_000006_add_d6_review_fields_to_target_group_rows.php');

        $this->runArtisan($database, [
            'migrate:rollback',
            '--database=sqlite',
            '--force',
            '--no-interaction',
            '--step=1',
        ], '000006 rollback');

        $this->assertColumnsAndIndexesAbsent($database, 'target_group_rows', [
            'review_status',
            'review_reason_code',
            'review_outcome',
            'reviewed_by',
            'reviewed_at',
            'matching_key_type',
            'matching_key_version',
            'normalization_version',
            'validation_version',
            'conflict_flags',
        ], [
            'target_group_rows_review_status_index',
            'target_group_rows_review_reason_code_index',
            'target_group_rows_review_status_target_group_job_id_index',
        ]);
    }

    public function test_000008_up_and_down_remove_all_d6_audit_objects_on_isolated_sqlite(): void
    {
        $database = $this->temporaryDatabase();
        $this->migrateThrough($database, '2026_08_07_000008_add_d6_context_to_audit_logs.php');

        $this->runArtisan($database, [
            'migrate:rollback',
            '--database=sqlite',
            '--force',
            '--no-interaction',
            '--step=1',
        ], '000008 rollback');

        $this->assertColumnsAndIndexesAbsent($database, 'audit_logs', [
            'correlation_id',
            'target_group_job_id',
            'target_group_file_id',
            'target_group_row_id',
            'matching_key_type',
            'matching_key_version',
            'review_reason_code',
            'review_outcome',
            'conflict_flags',
            'reviewed_by',
            'reviewed_at',
        ], [
            'audit_logs_correlation_id_index',
            'audit_logs_review_reason_code_index',
            'audit_logs_target_group_row_id_created_at_index',
        ]);
    }

    public function test_full_repository_can_migrate_rollback_and_migrate_again_on_isolated_sqlite(): void
    {
        $database = $this->temporaryDatabase();

        $this->runArtisan($database, [
            'migrate',
            '--database=sqlite',
            '--force',
            '--no-interaction',
        ], 'full migrate');

        $this->runArtisan($database, [
            'migrate:rollback',
            '--database=sqlite',
            '--force',
            '--no-interaction',
        ], 'full rollback');

        $this->runArtisan($database, [
            'migrate',
            '--database=sqlite',
            '--force',
            '--no-interaction',
        ], 'full re-migrate');

        $this->assertNotEmpty($this->sqliteTableNames($database));
    }

    protected function tearDown(): void
    {
        foreach ($this->temporaryDatabases as $database) {
            if (is_file($database)) {
                @unlink($database);
            }
        }

        parent::tearDown();
    }

    private function temporaryDatabase(): string
    {
        $database = tempnam(sys_get_temp_dir(), 'd6-migration-');
        $this->assertIsString($database);
        $this->temporaryDatabases[] = $database;

        return $database;
    }

    private function migrateThrough(string $database, string $targetMigration): void
    {
        $arguments = [
            'migrate',
            '--database=sqlite',
            '--force',
            '--no-interaction',
            '--step',
        ];

        foreach ($this->migrationPathsThrough($targetMigration) as $path) {
            $arguments[] = '--path='.$path;
        }

        $this->runArtisan($database, $arguments, 'migrate through '.$targetMigration);
    }

    /** @return list<string> */
    private function migrationPathsThrough(string $targetMigration): array
    {
        $paths = glob(database_path('migrations/*.php')) ?: [];
        usort($paths, static fn (string $left, string $right): int => strcmp(basename($left), basename($right)));

        $selected = [];
        foreach ($paths as $path) {
            $basename = basename($path);
            if ($basename > $targetMigration) {
                break;
            }

            $selected[] = 'database/migrations/'.$basename;
        }

        $this->assertContains('database/migrations/'.$targetMigration, $selected);

        return $selected;
    }

    /** @param list<string> $arguments */
    private function runArtisan(string $database, array $arguments, string $label): void
    {
        $environment = array_merge(getenv() ?: [], $_ENV, $_SERVER, [
            'APP_ENV' => 'testing',
            'APP_DEBUG' => 'false',
            'DB_CONNECTION' => 'sqlite',
            'DB_DATABASE' => $database,
            'CACHE_STORE' => 'array',
            'SESSION_DRIVER' => 'array',
            'QUEUE_CONNECTION' => 'sync',
        ]);

        $process = new Process(
            array_merge([PHP_BINARY, 'artisan'], $arguments),
            base_path(),
            $environment,
            null,
            300,
        );
        $exitCode = $process->run();

        $this->assertSame(
            0,
            $exitCode,
            $label." failed (exit {$exitCode}).\nSTDOUT:\n{$process->getOutput()}\nSTDERR:\n{$process->getErrorOutput()}"
        );
    }

    /** @param list<string> $columns @param list<string> $indexes */
    private function assertColumnsAndIndexesAbsent(string $database, string $table, array $columns, array $indexes): void
    {
        $pdo = new PDO('sqlite:'.$database);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

        $actualColumns = array_map(
            static fn (array $row): string => (string) $row['name'],
            $pdo->query('PRAGMA table_info("'.$table.'")')->fetchAll(PDO::FETCH_ASSOC),
        );
        $actualIndexes = array_map(
            static fn (array $row): string => (string) $row['name'],
            $pdo->query('SELECT name FROM sqlite_master WHERE type = \'index\' AND tbl_name = '. $pdo->quote($table))->fetchAll(PDO::FETCH_ASSOC),
        );

        foreach ($columns as $column) {
            $this->assertNotContains($column, $actualColumns, "Column {$table}.{$column} remained after rollback.");
        }

        foreach ($indexes as $index) {
            $this->assertNotContains($index, $actualIndexes, "Index {$index} remained after rollback.");
        }
    }

    /** @return list<string> */
    private function sqliteTableNames(string $database): array
    {
        $pdo = new PDO('sqlite:'.$database);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

        return array_map(
            static fn (array $row): string => (string) $row['name'],
            $pdo->query("SELECT name FROM sqlite_master WHERE type = 'table'")->fetchAll(PDO::FETCH_ASSOC),
        );
    }
}
