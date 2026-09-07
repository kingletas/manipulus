<?php
/**
 * @package   Manipulus_Bundles
 * @copyright Copyright (c) 2026 Luis Tineo
 * @license   MIT https://opensource.org/licenses/MIT
 */

declare(strict_types=1);

/**
 * Puts the Magento classes on an autoloader, from whichever tree has them.
 */

// Loading both trees is not an option: two copies of magento/framework
// redeclare every class and the run dies before the first test.

$moduleDir = dirname(__DIR__);
$ownVendor = $moduleDir . '/vendor';
$borrowed = getenv('M2_VENDOR') ?: '';

$haveOwn = is_file($ownVendor . '/autoload.php') && is_dir($ownVendor . '/magento/framework');
$haveBorrowed = $borrowed !== '' && is_dir($borrowed . '/magento/framework');

if (!$haveOwn && !$haveBorrowed) {
    fwrite(
        STDERR,
        "No Magento framework to test against.\n\n"
        . "  Either:  composer install            (needs repo.magento.com credentials)\n"
        . "  or:      M2_VENDOR=/path/to/magento/vendor vendor/bin/phpunit\n"
    );

    exit(1);
}

if ($haveOwn) {
    $loader = require $ownVendor . '/autoload.php';
    $vendorDir = $ownVendor;
} else {
    require_once $ownVendor . '/autoload.php';

    $loader = new \Composer\Autoload\ClassLoader($borrowed);
    $vendorDir = $borrowed;

    /** @var array<string, string[]> $psr4 */
    $psr4 = require $borrowed . '/composer/autoload_psr4.php';

    foreach ($psr4 as $namespace => $paths) {
        $loader->setPsr4($namespace, $paths);
    }

    $loader->addClassMap(require $borrowed . '/composer/autoload_classmap.php');
    $loader->register(true);

    if (is_file($borrowed . '/magento/framework/Phrase/__.php')) {
        require_once $borrowed . '/magento/framework/Phrase/__.php';
    }
}

// The module under test, read from its own manifest so the two cannot disagree.
$manifest = json_decode((string) file_get_contents($moduleDir . '/composer.json'), true);

foreach ($manifest['autoload']['psr-4'] ?? [] as $namespace => $relative) {
    $loader->setPsr4($namespace, [rtrim($moduleDir . '/' . $relative, '/')]);
}

if (!defined('BP')) {
    define('BP', dirname($vendorDir));
}
