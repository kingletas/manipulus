<?php
/**
 * @package   Manipulus_Bundles
 * @copyright Copyright (c) 2026 Luis Tineo
 * @license   MIT https://opensource.org/licenses/MIT
 */

declare(strict_types=1);

namespace Manipulus\Bundles\Test\Unit;

use Magento\Framework\App\Config\ScopeConfigInterface;
use Magento\Framework\App\Filesystem\DirectoryList;
use Magento\Framework\App\State;
use Magento\Framework\Code\Minifier\AdapterInterface;
use Magento\Framework\Filesystem;
use Magento\Framework\Filesystem\Directory\ReadInterface;
use Magento\Framework\Filesystem\Driver\File as FileDriver;
use Magento\Framework\Filesystem\File\ReadFactory;
use Magento\Framework\RequireJs\Config as RequireJsConfig;
use Magento\Framework\RequireJs\Config\File\Collector\Aggregated;
use Magento\Framework\Serialize\Serializer\Json;
use Magento\Framework\View\Asset\Minification;
use Magento\Framework\View\Asset\Repository;
use Magento\Framework\View\Asset\RepositoryMap;
use Magento\Framework\View\DesignInterface;
use Manipulus\Bundles\Model\DeployedBundles;
use PHPUnit\Framework\TestCase;

/**
 * The minification exclusion in etc/config.xml against the Magento code that reads it.
 */
class MinifyExcludeTest extends TestCase
{
    private const STATIC_PATH = 'frontend/Magento/luma/en_US';

    private const BUNDLE = self::STATIC_PATH . '/' . DeployedBundles::DIRECTORY . '/bundle-common.js';

    private const MODULE_FILE = self::STATIC_PATH . '/mage/common.js';

    private const BASE_URL = 'https://store.test/static/version1/';

    public function testTheExclusionIsDeclaredForJavaScript(): void
    {
        $this->assertNotEmpty($this->declaredExcludes());
    }

    public function testWithMinificationOnABundleKeepsItsPlainName(): void
    {
        $minification = $this->minification(true);

        $this->assertSame(self::BUNDLE, $minification->addMinifiedSign(self::BUNDLE));
        $this->assertSame(
            self::STATIC_PATH . '/mage/common.min.js',
            $minification->addMinifiedSign(self::MODULE_FILE),
            'minification is not on, so the first assertion proves nothing'
        );
    }

    public function testWithMinificationOffNothingIsRenamed(): void
    {
        $minification = $this->minification(false);

        $this->assertSame(self::BUNDLE, $minification->addMinifiedSign(self::BUNDLE));
        $this->assertSame(self::MODULE_FILE, $minification->addMinifiedSign(self::MODULE_FILE));
    }

    public function testTheResolverRequireJsRunsLeavesBundleUrlsAlone(): void
    {
        $code = $this->resolverCode($this->minification(true));

        $this->assertFalse($this->resolverRewrites($code, self::BASE_URL . self::BUNDLE));
        $this->assertTrue(
            $this->resolverRewrites($code, self::BASE_URL . self::MODULE_FILE),
            'the resolver rewrites nothing, so the first assertion proves nothing'
        );
    }

    public function testTheGuardLooksForThePlainNameWhenMinifying(): void
    {
        $this->assertGuardLooksFor(self::BUNDLE, $this->minification(true));
    }

    public function testTheGuardLooksForThePlainNameWithoutMinifying(): void
    {
        $this->assertGuardLooksFor(self::BUNDLE, $this->minification(false));
    }

    private function assertGuardLooksFor(string $file, Minification $minification): void
    {
        $static = $this->createMock(ReadInterface::class);
        $static->expects($this->once())->method('isFile')->with($file)->willReturn(true);
        $filesystem = $this->createMock(Filesystem::class);
        $filesystem->method('getDirectoryRead')->with(DirectoryList::STATIC_VIEW)->willReturn($static);
        $driver = $this->createMock(FileDriver::class);
        $driver->method('fileGetContents')
            ->willReturn('var config = {"bundles": {"manipulus/bundle-common": ["jquery"]}};');

        $bundles = new DeployedBundles($filesystem, $driver, new Json(), $minification);

        $this->assertTrue($bundles->areDeployed('requirejs-config.js', self::STATIC_PATH));
    }

    /**
     * Mirrors the condition in RequireJs\Config::getMinResolverCode() for one URL.
     */
    private function resolverRewrites(string $code, string $url): bool
    {
        $this->assertStringContainsString('url.indexOf(baseUrl)===0', $code);
        preg_match_all('#!url\.match\((/.+?[^\\\\]/)\)#', $code, $matches);

        foreach ($matches[1] as $expression) {
            if (preg_match($expression, $url) === 1) {
                return false;
            }
        }

        return str_starts_with($url, self::BASE_URL);
    }

    private function resolverCode(Minification $minification): string
    {
        $adapter = $this->createMock(AdapterInterface::class);
        $adapter->method('minify')->willReturnArgument(0);

        $config = new RequireJsConfig(
            $this->createMock(Aggregated::class),
            $this->createMock(DesignInterface::class),
            $this->createMock(ReadFactory::class),
            $this->createMock(Repository::class),
            $adapter,
            $minification,
            $this->createMock(RepositoryMap::class)
        );

        return $config->getMinResolverCode();
    }

    private function minification(bool $enabled): Minification
    {
        $state = $this->createMock(State::class);
        $state->method('getMode')->willReturn(State::MODE_PRODUCTION);

        // Magento_Store ships its own exclusion; config merging puts ours beside it.
        $excludes = ['hugerte' => '/hugerte/'] + $this->declaredExcludes();

        $scopeConfig = $this->createMock(ScopeConfigInterface::class);
        $scopeConfig->method('isSetFlag')->willReturnMap([
            ['dev/js/minify_files', 'store', null, $enabled],
        ]);
        $scopeConfig->method('getValue')->willReturnMap([
            ['dev/js/minify_exclude', 'store', null, $excludes],
        ]);

        return new Minification($scopeConfig, $state);
    }

    /**
     * @return array<string, string>
     */
    private function declaredExcludes(): array
    {
        $config = simplexml_load_file(dirname(__DIR__, 2) . '/etc/config.xml');
        $this->assertNotFalse($config, 'etc/config.xml is not parsable XML');

        $excludes = [];
        foreach ($config->xpath('/config/default/dev/js/minify_exclude/*') ?: [] as $exclude) {
            $excludes[$exclude->getName()] = trim((string) $exclude);
        }

        return $excludes;
    }
}
