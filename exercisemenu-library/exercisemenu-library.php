<?php
/**
 * Plugin Name: ExerciseMenu Library
 * Description: Exercise guides and workout routines with linked exercise tables, GIF/video demos and index control.
 * Version:     0.1.0
 * Requires at least: 6.2
 * Requires PHP: 7.4
 * Author:      ExerciseMenu
 * License:     GPL-2.0-or-later
 * Text Domain: exercisemenu-library
 */

defined( 'ABSPATH' ) || exit;

define( 'EM_LIB_VERSION', '0.1.0' );
define( 'EM_LIB_FILE', __FILE__ );
define( 'EM_LIB_DIR', plugin_dir_path( __FILE__ ) );
define( 'EM_LIB_URL', plugin_dir_url( __FILE__ ) );

require_once EM_LIB_DIR . 'includes/class-post-types.php';
require_once EM_LIB_DIR . 'includes/class-routine-plan.php';
require_once EM_LIB_DIR . 'includes/class-meta.php';
require_once EM_LIB_DIR . 'includes/class-render.php';
require_once EM_LIB_DIR . 'includes/class-library.php';
require_once EM_LIB_DIR . 'includes/class-seo.php';
require_once EM_LIB_DIR . 'includes/class-importer.php';
require_once EM_LIB_DIR . 'includes/class-admin.php';

EM_Post_Types::init();
EM_Meta::init();
EM_Render::init();
EM_Library::init();
EM_SEO::init();
EM_Admin::init();

if ( defined( 'WP_CLI' ) && WP_CLI ) {
	require_once EM_LIB_DIR . 'includes/class-cli.php';
	WP_CLI::add_command( 'em-library', 'EM_CLI' );
}

register_activation_hook(
	__FILE__,
	function () {
		EM_Post_Types::register();
		flush_rewrite_rules();
	}
);

register_deactivation_hook( __FILE__, 'flush_rewrite_rules' );
