<?php
/**
 * @package   Manipulus_Bundles
 * @copyright Copyright (c) 2026 Luis Tineo
 * @license   MIT https://opensource.org/licenses/MIT
 */

declare(strict_types=1);

namespace Manipulus\Bundles\Test\Unit\Model;

use Magento\Framework\App\Filesystem\DirectoryList;
use Magento\Framework\Filesystem;
use Magento\Framework\Filesystem\Directory\WriteInterface;
use Magento\Framework\Serialize\Serializer\Json;
use Manipulus\Bundles\Model\IntegrityHashes;
use PHPUnit\Framework\TestCase;

class IntegrityHashesTest extends TestCase
{
    private const HASH_FILE = 'frontend/sri-hashes.json';
    private const KEY = 'frontend/Magento/luma/en_US/requirejs-config.js';
    private const CONTENTS = 'require.config({});';

    /**
     * The hash Magento records is the base64 of the raw sha256, prefixed.
     */
    private function expectedHash(string $contents): string
    {
        return 'sha256-' . base64_encode(hash('sha256', $contents, true));
    }

    /**
     * @param array<string, string> $recorded
     */
    private function build(array $recorded, ?string $deployed = self::CONTENTS): array
    {
        $static = $this->createMock(WriteInterface::class);
        $static->method('search')->willReturn([self::HASH_FILE]);
        $static->method('isExist')->willReturnCallback(
            static fn (string $path): bool => $deployed !== null && $path === self::KEY
        );
        $static->method('readFile')->willReturnCallback(
            static function (string $path) use ($recorded, $deployed) {
                return $path === self::HASH_FILE ? json_encode($recorded) : (string) $deployed;
            }
        );

        $filesystem = $this->createMock(Filesystem::class);
        $filesystem->method('getDirectoryWrite')
            ->with(DirectoryList::STATIC_VIEW)
            ->willReturn($static);

        $json = $this->createMock(Json::class);
        $json->method('unserialize')->willReturnCallback(
            static fn (string $value): array => (array) json_decode($value, true)
        );
        $json->method('serialize')->willReturnCallback(
            static fn ($value): string => (string) json_encode($value)
        );

        return [new IntegrityHashes($filesystem, $json), $static];
    }

    public function testAHashThatAlreadyMatchesIsLeftAlone(): void
    {
        [$hashes, $static] = $this->build([self::KEY => $this->expectedHash(self::CONTENTS)]);
        $static->expects($this->never())->method('writeFile');

        $this->assertSame(['refreshed' => [], 'missing' => []], $hashes->refresh());
    }

    public function testAStaleHashIsRefreshed(): void
    {
        [$hashes, $static] = $this->build([self::KEY => 'sha256-obviously-wrong']);
        $static->expects($this->once())->method('writeFile');

        $result = $hashes->refresh();

        $this->assertSame([self::KEY], $result['refreshed']);
        $this->assertSame([], $result['missing']);
    }

    public function testADryRunReportsWithoutWriting(): void
    {
        [$hashes, $static] = $this->build([self::KEY => 'sha256-obviously-wrong']);
        $static->expects($this->never())->method('writeFile');

        $this->assertSame([self::KEY], $hashes->refresh(true)['refreshed']);
    }

    public function testAHashedFileThatIsNoLongerDeployedIsReportedNotSilentlySkipped(): void
    {
        [$hashes, $static] = $this->build([self::KEY => 'sha256-anything'], null);
        $static->expects($this->never())->method('writeFile');

        $result = $hashes->refresh();

        $this->assertSame([self::KEY], $result['missing']);
        $this->assertSame([], $result['refreshed']);
    }

    public function testAKeyAlreadyCarryingItsAreaIsNotPrefixedTwice(): void
    {
        [$hashes] = $this->build([self::KEY => 'sha256-obviously-wrong']);

        // The key already starts with `frontend/`, and the hash file lives in
        // `frontend/`. Prefixing again would look for frontend/frontend/...
        $this->assertSame([self::KEY], $hashes->refresh()['refreshed']);
    }
}
