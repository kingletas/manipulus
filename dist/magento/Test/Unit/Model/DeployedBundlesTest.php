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
use Magento\Framework\Filesystem\Directory\ReadInterface;
use Magento\Framework\Filesystem\Driver\File as FileDriver;
use Magento\Framework\Serialize\Serializer\Json;
use Magento\Framework\View\Asset\Minification;
use Manipulus\Bundles\Model\DeployedBundles;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class DeployedBundlesTest extends TestCase
{
    private const STATIC_PATH = 'frontend/Magento/luma/en_US';

    private const ONE_BUNDLE = 'var config = {"bundles": {"manipulus/bundle-common": ["jquery"]}};';

    public function testTheShippedEmptyMapNamesNothingSoThereIsNothingToMiss(): void
    {
        $static = $this->createMock(ReadInterface::class);
        $static->expects($this->never())->method('isFile');
        $shipped = dirname(__DIR__, 3) . '/view/frontend/requirejs-config.js';

        $bundles = $this->build($static, new FileDriver());

        $this->assertTrue($bundles->areDeployed($shipped, self::STATIC_PATH));
    }

    public function testTheFileCheckedIsTheOneMinificationMakesRequireJsAskFor(): void
    {
        $static = $this->createMock(ReadInterface::class);
        $static->expects($this->once())
            ->method('isFile')
            ->with(self::STATIC_PATH . '/manipulus/bundle-common.min.js')
            ->willReturn(false);
        $minification = $this->createMock(Minification::class);
        $minification->method('addMinifiedSign')->willReturnCallback(
            static fn (string $file): string => substr($file, 0, -3) . '.min.js'
        );

        $bundles = $this->build($static, $this->driverReturning(self::ONE_BUNDLE), $minification);

        $this->assertFalse($bundles->areDeployed('requirejs-config.js', self::STATIC_PATH));
    }

    /**
     * @return array<string, string[]>
     */
    public static function unreadableConfigs(): array
    {
        return [
            'not a config at all' => ['// someone edited this by hand'],
            'not JSON' => ['var config = { bundles: { common: [] } };'],
            'no bundles key' => ['var config = {"paths": {}};'],
            'an id outside the bundle directory' => ['var config = {"bundles": {"../../../etc/bundle-x": []}};'],
        ];
    }

    #[DataProvider('unreadableConfigs')]
    public function testAConfigItCannotReadIsNotVouchedFor(string $config): void
    {
        $static = $this->createMock(ReadInterface::class);
        $static->expects($this->never())->method('isFile');

        $bundles = $this->build($static, $this->driverReturning($config));

        $this->assertFalse($bundles->areDeployed('requirejs-config.js', self::STATIC_PATH));
    }

    private function driverReturning(string $config): FileDriver
    {
        $driver = $this->createMock(FileDriver::class);
        $driver->method('fileGetContents')->willReturn($config);

        return $driver;
    }

    private function build(
        ReadInterface $static,
        FileDriver $driver,
        ?Minification $minification = null
    ): DeployedBundles {
        $filesystem = $this->createMock(Filesystem::class);
        $filesystem->method('getDirectoryRead')->with(DirectoryList::STATIC_VIEW)->willReturn($static);

        if ($minification === null) {
            $minification = $this->createMock(Minification::class);
            $minification->method('addMinifiedSign')->willReturnArgument(0);
        }

        return new DeployedBundles($filesystem, $driver, new Json(), $minification);
    }
}
