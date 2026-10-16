<?php
/**
 * Post types and taxonomies.
 *
 * URLs:
 *   /exercises/{slug}/                 single exercise
 *   /exercises/muscle/{term}/          exercises by target muscle
 *   /exercises/equipment/{term}/       exercises by equipment
 *   /workout-routines/{slug}/          single routine
 *   /workout-routines/goal/{term}/     routines by goal
 *
 * /exercises/ and /workout-routines/ themselves are normal WordPress pages
 * holding the [em_exercise_library] / [em_routine_library] shortcodes, so the
 * post types have no archive of their own.
 */

defined( 'ABSPATH' ) || exit;

class EM_Post_Types {

	const EXERCISE = 'em_exercise';
	const ROUTINE  = 'em_routine';

	public static function init() {
		add_action( 'init', array( __CLASS__, 'register' ) );
	}

	public static function register() {
		// Taxonomies go first: their rewrite rules must sit above the post type
		// rules, or /exercises/muscle/chest/ is read as an exercise attachment.
		self::taxonomy( 'em_muscle', array( self::EXERCISE ), 'exercises/muscle', 'Target muscles', 'Target muscle', 'muscle' );
		self::taxonomy( 'em_equipment', array( self::EXERCISE, self::ROUTINE ), 'exercises/equipment', 'Equipment', 'Equipment', 'equipment' );
		self::taxonomy( 'em_level', array( self::EXERCISE, self::ROUTINE ), 'exercises/level', 'Levels', 'Level', 'level' );
		self::taxonomy( 'em_goal', array( self::ROUTINE ), 'workout-routines/goal', 'Goals', 'Goal', 'goal' );

		register_post_type(
			self::EXERCISE,
			array(
				'labels'        => self::labels( 'Exercises', 'Exercise' ),
				'public'        => true,
				'has_archive'   => false,
				'show_in_rest'  => true,
				'menu_icon'     => 'dashicons-universal-access',
				'menu_position' => 21,
				'rewrite'       => array( 'slug' => 'exercises', 'with_front' => false ),
				'supports'      => array( 'title', 'editor', 'excerpt', 'thumbnail', 'author', 'revisions', 'custom-fields' ),
			)
		);

		register_post_type(
			self::ROUTINE,
			array(
				'labels'        => self::labels( 'Workout Routines', 'Workout Routine' ),
				'public'        => true,
				'has_archive'   => false,
				'show_in_rest'  => true,
				'menu_icon'     => 'dashicons-list-view',
				'menu_position' => 22,
				'rewrite'       => array( 'slug' => 'workout-routines', 'with_front' => false ),
				'supports'      => array( 'title', 'editor', 'excerpt', 'thumbnail', 'author', 'revisions', 'custom-fields' ),
			)
		);
	}

	private static function taxonomy( $name, $post_types, $slug, $plural, $singular, $query_var ) {
		register_taxonomy(
			$name,
			$post_types,
			array(
				'labels'            => self::labels( $plural, $singular ),
				'public'            => true,
				'hierarchical'      => false,
				'show_in_rest'      => true,
				'show_admin_column' => true,
				'query_var'         => $query_var,
				'rewrite'           => array( 'slug' => $slug, 'with_front' => false ),
			)
		);
	}

	private static function labels( $plural, $singular ) {
		return array(
			'name'          => $plural,
			'singular_name' => $singular,
			'add_new_item'  => 'Add New ' . $singular,
			'edit_item'     => 'Edit ' . $singular,
			'new_item'      => 'New ' . $singular,
			'view_item'     => 'View ' . $singular,
			'search_items'  => 'Search ' . $plural,
			'not_found'     => 'No ' . strtolower( $plural ) . ' found',
			'all_items'     => 'All ' . $plural,
			'menu_name'     => $plural,
		);
	}
}
