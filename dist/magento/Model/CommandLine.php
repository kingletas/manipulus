<?php
/**
 * @package   Manipulus_Bundles
 * @copyright Copyright (c) 2026 Luis Tineo
 */

declare(strict_types=1);

namespace Manipulus\Bundles\Model;

/**
 * Says whether PHP is running on the command line, which is where Magento's static content deploy runs.
 */
class CommandLine
{
    private const SAPI = 'cli';

    /**
     * Read on every call: a constructor default would be frozen into compiled DI as the compiler's own SAPI.
     */
    public function isCurrent(): bool
    {
        return PHP_SAPI === self::SAPI;
    }
}
