<?php
/**
 * @package   Manipulus_Bundles
 * @copyright Copyright (c) 2026 Luis Tineo
 * @license   MIT https://opensource.org/licenses/MIT
 */

declare(strict_types=1);

namespace Manipulus\Bundles\Test\Unit\Console\Command;

use Magento\Framework\App\Filesystem\DirectoryList;
use Magento\Framework\Filesystem;
use Magento\Framework\Filesystem\Directory\ReadInterface;
use Manipulus\Bundles\Console\Command\ShowBundlesCommand;
use PHPUnit\Framework\TestCase;
use Symfony\Component\Console\Tester\CommandTester;

class ShowBundlesCommandTest extends TestCase
{
    /**
     * @param string[] $found
     * @param array<string, int> $sizes
     */
    private function tester(array $found, array $sizes = []): CommandTester
    {
        $static = $this->createMock(ReadInterface::class);
        $static->method('search')->willReturn($found);
        $static->method('stat')->willReturnCallback(
            static fn (string $path): array => ['size' => $sizes[$path] ?? 0]
        );

        $filesystem = $this->createMock(Filesystem::class);
        $filesystem->method('getDirectoryRead')
            ->with(DirectoryList::STATIC_VIEW)
            ->willReturn($static);

        return new CommandTester(new ShowBundlesCommand($filesystem));
    }

    public function testItSaysSoWhenNothingIsDeployed(): void
    {
        $tester = $this->tester([]);
        $tester->execute([]);

        $this->assertStringContainsString('No bundles are deployed', $tester->getDisplay());
        $this->assertSame(0, $tester->getStatusCode());
    }

    public function testItListsEachBundleAndTotalsThem(): void
    {
        $common = 'frontend/Magento/luma/en_US/manipulus/bundle-common.js';
        $product = 'frontend/Magento/luma/en_US/manipulus/bundle-product.js';

        $tester = $this->tester([$common, $product], [$common => 2048, $product => 1024]);
        $tester->execute([]);

        $display = $tester->getDisplay();
        $this->assertStringContainsString('bundle-common.js', $display);
        $this->assertStringContainsString('bundle-product.js', $display);
        $this->assertStringContainsString('2 bundle(s), 3 kB', $display);
    }

    public function testTheCommandOwnsItsName(): void
    {
        $command = new ShowBundlesCommand($this->createMock(Filesystem::class));

        $this->assertSame(ShowBundlesCommand::NAME, $command->getName());
        $this->assertSame('manipulus:bundles:show', $command->getName());
    }
}
