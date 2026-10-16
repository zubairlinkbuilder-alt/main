<?php
/**
 * WP-CLI: wp em-library import
 */

defined( 'ABSPATH' ) || exit;

class EM_CLI {

	/**
	 * Imports the bundled exercises and routines as drafts. Existing slugs are skipped.
	 *
	 * @when after_wp_load
	 */
	public function import() {
		$report = EM_Importer::run();
		foreach ( $report['errors'] as $error ) {
			WP_CLI::warning( $error );
		}
		WP_CLI::success( sprintf( '%d created, %d skipped (already exist).', count( $report['created'] ), count( $report['skipped'] ) ) );
	}
}
