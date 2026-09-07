<?php
/**
 * @package   Manipulus_Bundles
 * @copyright Copyright (c) 2026 Luis Tineo
 * @license   MIT https://opensource.org/licenses/MIT
 */

declare(strict_types=1);

namespace Manipulus\Bundles\Test\Unit\Console\Command;

use Manipulus\Bundles\Console\Command\RefreshIntegrityCommand;
use Manipulus\Bundles\Model\IntegrityHashes;
use PHPUnit\Framework\TestCase;
use Symfony\Component\Console\Tester\CommandTester;

class RefreshIntegrityCommandTest extends TestCase
{
    /**
     * @param array<string, string[]> $result
     */
    private function tester(array $result, bool $expectDryRun = false): CommandTester
    {
        $hashes = $this->createMock(IntegrityHashes::class);
        $hashes->expects($this->once())
            ->method('refresh')
            ->with($expectDryRun)
            ->willReturn($result);

        return new CommandTester(new RefreshIntegrityCommand($hashes));
    }

    public function testItSaysNothingWhenEveryHashAlreadyAgrees(): void
    {
        $tester = $this->tester(['refreshed' => [], 'missing' => []]);
        $tester->execute([]);

        $this->assertSame('', trim($tester->getDisplay()));
        $this->assertSame(0, $tester->getStatusCode());
    }

    public function testItNamesEveryHashItRefreshed(): void
    {
        $tester = $this->tester(['refreshed' => ['frontend/a.js', 'frontend/b.js'], 'missing' => []]);
        $tester->execute([]);

        $display = $tester->getDisplay();
        $this->assertStringContainsString('refreshed frontend/a.js', $display);
        $this->assertStringContainsString('refreshed frontend/b.js', $display);
        $this->assertStringContainsString('2 hash(es) refreshed.', $display);
    }

    public function testADryRunSaysWhatItWouldDoRatherThanWhatItDid(): void
    {
        $tester = $this->tester(['refreshed' => ['frontend/a.js'], 'missing' => []], true);
        $tester->execute(['--dry-run' => true]);

        $display = $tester->getDisplay();
        $this->assertStringContainsString('would refresh frontend/a.js', $display);
        $this->assertStringContainsString('would be refreshed', $display);
    }

    public function testAHashedFileThatIsGoneIsReported(): void
    {
        $tester = $this->tester(['refreshed' => [], 'missing' => ['frontend/gone.js']]);
        $tester->execute([]);

        $this->assertStringContainsString('hashed but not deployed: frontend/gone.js', $tester->getDisplay());
    }

    public function testTheCommandOwnsItsName(): void
    {
        // A rename would break every pipeline that calls it, so it is a constant
        // rather than something a deployment can quietly change.
        $command = new RefreshIntegrityCommand($this->createMock(IntegrityHashes::class));

        $this->assertSame(RefreshIntegrityCommand::NAME, $command->getName());
        $this->assertSame('manipulus:integrity:refresh', $command->getName());
    }
}
