from itertools import islice
import math
import os
import random
import sys

import pygame

from .StateHandler import StateHandler
from Graphics.LevelMap import LevelMap
from Math.Vector2 import Vector2
from Objects.GameObject import GameObject
from Objects.Player import Player
from Objects.Teleporter import Teleporter
from Objects.Turret import Turret
from Objects.Laser import Laser
from Utilities.CollisionDetection import MoveDirection
from Utilities.Pathing import Pathing

## The handler class for controlling a level of the game.
## \author  Michael Watkinson
## \date    09/01/2018
class LevelHandler(StateHandler):
    ## Initializes the level handler.
    ## \param[in]  game_window - The GameWindow object to display the level on.
    ## \param[in]   level_filepath - The filepath of the level to load.  Defaults to None.
    ##      If None is provided, the first level will be played.
    ## \author  Michael Watkinson
    ## \date    09/01/2018
    def __init__(self, game_window, level_filepath = None):
        # INITIALIZE THE HANDLER.
        # Only initialize the background music for the first level.
        # It will be kept running throughout the game.
        audio = None
        level_filepath = level_filepath if (level_filepath is not None) else '../Maps/Level1.txt'
        start_background_music = ('Level1' in level_filepath)
        if start_background_music:
            audio = {
                'BackgroundMusic': '../Audio/background_music.mp3'}
        StateHandler.__init__(self, audio = audio)
        
        # INITIALIZE INSTANCE VARIABLES.
        self.GameWindow = game_window
        self.LevelFilepath = level_filepath
        self.Map = LevelMap(self.LevelFilepath)
        self.Pathing = Pathing(self.Map)

    ## Runs the level and and handles displaying all graphics, playing sounds, and player interaction.
    ## \return  The next StateHandler class to be run in the main game loop.
    ## \author  Michael Watkinson
    ## \date    09/01/2018
    def Run(self):
        # HANDLE INTERACTION.
        # The clock is used to determine elapsed time between frames.
        clock = pygame.time.Clock()
        while True:
            # UPDATE THE GAME CLOCK.
            # Ticking will automatically delay the game if needed to achieve the desired frame rate.
            time_since_last_update_in_ms = clock.tick(self.MaxFramesPerSecond)
            MILLISECONDS_PER_SECOND = 1000
            time_since_last_update_in_seconds = (time_since_last_update_in_ms / MILLISECONDS_PER_SECOND)

            # UPDATE THE TELEPORTER.
            teleporter = self.Map.GetTeleporter()
            teleporter_activated = False
            if teleporter is not None:
                # Update the teleporter animation.
                enemies = self.Map.GetEnemies()
                enemy_count = len(enemies)
                teleporter.Update(time_since_last_update_in_seconds, enemy_count)
                teleporter_activated = teleporter.Activated

            # HANDLE PLAYER INTERACTION.
            # This must be performed after updating the teleporter because when the player walks into the teleporter
            # it will be removed from the map since two objects cannot occupy the same space.
            collided_with_teleporter, player_alive = self.HandlePlayerInteraction(teleporter_activated)
            
            # Check if the player is still alive.
            if not player_alive:
                # The player died, so restart the current level.
                return LevelHandler(self.GameWindow, self.LevelFilepath)
            
            # Check if we should move to the next level.
            move_to_next_level = (collided_with_teleporter and teleporter_activated)
            if move_to_next_level:
                # Form the filepath for the next level.
                # Increment the level number in the filename by 1.
                next_level_index = (int(os.path.basename(self.LevelFilepath).replace('Level', '').replace('.txt', '')) + 1)
                next_level_filepath = os.path.join(os.path.dirname(self.LevelFilepath), 'Level{}.txt'.format(next_level_index))
                
                # Prepare the handler for the next level.
                return LevelHandler(self.GameWindow, next_level_filepath)
            
            # ALLOW ENEMIES TO REACT TO THE PLAYER.
            self.UpdateEnemies(time_since_last_update_in_seconds)

            # UPDATE THE LASERS.
            for laser in self.Map.Lasers:
                laser.Update(time_since_last_update_in_seconds)
                
                # Remove lasers that are hitting a wall.
                walls = self.Map.GetWalls()
                for wall in walls:
                    laser_hit_wall = wall.Coordinates.colliderect(laser.Coordinates)
                    if laser_hit_wall:
                        # REMOVE THE LASER FROM THE MAP.
                        try:
                            self.Map.Lasers.remove(laser)
                        except:
                            pass
                
            # Any lasers that are no longer in bounds should be removed.
            self.Map.Lasers = [laser for laser in self.Map.Lasers if self.Map.ObjectInBounds(laser)]

            # UPDATE THE PLAYER.
            player = self.Map.GetPlayer()
            if player is not None:
                player.Update()

                # The sword's handle position should follow the player when the player moves.
                player.Sword.HandleScreenPosition = player.HandScreenPosition
                player.Sword.Update(time_since_last_update_in_seconds)

                # HANDLE SWORD COLLISIONS IF THE SWORD IS OUT.
                if player.Sword.IsSwinging:
                    # CHECK FOR COLLISIONS OF THE SWORD WITH LASERS.
                    for laser in self.Map.Lasers:
                        # DETERMINE IF THE SWORD HIT THE PROJECTILE.
                        sword_bounding_rectangle = player.Sword.BoundingScreenRectangle
                        projectile_rectangle = laser.Coordinates
                        sword_collides_with_projectile = sword_bounding_rectangle.colliderect(projectile_rectangle)
                        if sword_collides_with_projectile:
                            # REFLECT THE PROJECTILE.
                            laser.Reflect()

            # UPDATE THE SCREEN.
            self.GameWindow.Update(self.Map)
           
    ## Handles player input from events, key presses and mouse interaction.
    ## \param[in]  teleporter_activated - A boolean to determine if the player can us the teleporter.
    ## \return  A two-tuple of booleans for whether or not the player used the teleporter and if the player is alive.
    ## \author  Michael Watkinson
    ## \date    09/01/2018
    def HandlePlayerInteraction(self, teleporter_activated):
        # GET THE PLAYER OBJECT FROM THE MAP.
        player = self.Map.GetPlayer()

        # HANDLE QUIT EVENTS.
        for event in pygame.event.get():
            # Check if the X button of the window was clicked.
            if event.type is pygame.QUIT:
                # Quit the game.
                pygame.quit()
                sys.exit()
                
            # Check if a key was newly pressed down.
            if event.type is pygame.KEYDOWN:
                if event.key is pygame.K_ESCAPE:
                    sys.exit()
                    pygame.quit()
            elif event.type is pygame.MOUSEBUTTONDOWN:
                # SWING THE PLAYER'S SWORD.
                player.SwingSword()
        
        # DETERMINE THE GAME OBJECTS THE PLAYER CAN COLLIDE WITH.
        allowed_collision_classes = ()
        if teleporter_activated:
            allowed_collision_classes = (Teleporter)
        
        # HANDLE PLAYER MOVEMENT.
        collided_object = None
        currently_pressed_keys = pygame.key.get_pressed()
        if currently_pressed_keys[pygame.K_w]:
            collided_object = player.MoveUp(self.Map, allowed_collision_classes)
        if currently_pressed_keys[pygame.K_a]:
            collided_object = player.MoveLeft(self.Map, allowed_collision_classes)
        if currently_pressed_keys[pygame.K_s]:
            collided_object = player.MoveDown(self.Map, allowed_collision_classes)
        if currently_pressed_keys[pygame.K_d]:
            collided_object = player.MoveRight(self.Map, allowed_collision_classes)

        # CHECK IF THE PLAYER HIT ANY LASERS.
        for laser in self.Map.Lasers:
            player_hit_laser = player.Coordinates.colliderect(laser.Coordinates)
            if player_hit_laser:
                # REMOVE THE LASER FROM THE MAP.
                self.Map.Lasers.remove(laser)

                # INDICATE THAT THE PLAYER DIED.
                collided_with_teleporter = False
                player_alive = False
                return (collided_with_teleporter, player_alive)
            
        # HANDLE USING TELEPORTER.
        collided_with_teleporter = isinstance(collided_object, Teleporter)
        player_alive = True
        return (collided_with_teleporter, player_alive)

    ## Causes enemies to move, shoot, or perform other actions.
    ## \param[in]   time_since_last_update_in_seconds - The time since the last enemy update, in seconds.
    ## \author  Tom Rogan
    ## \date    09/01/2018
    def UpdateEnemies(self, time_since_last_update_in_seconds):
        # UPDATE EACH ENEMY.
        player = self.Map.GetPlayer()
        player_position = self.Map.GetGridPosition(player.Coordinates.center)
        player_position_vector = Vector2(player_position[0], player_position[1])
        enemies = self.Map.GetEnemies()
        for enemy in enemies:
            # CHECK IF THE ENEMY WAS HIT BY A REFLECTED LASER.
            lasers_that_kill_enemy = [laser for laser in self.Map.Lasers
                if laser.HasBeenReflected and enemy.Coordinates.colliderect(laser.Coordinates)]
            enemy_was_hit_by_laser = (len(lasers_that_kill_enemy) > 0)
            if enemy_was_hit_by_laser:
                # Remove this enemy from the map.
                self.Map.RemoveObject(enemy)
                
                # No further updates are necessary for this enemy.
                continue

            # TARGET THE PLAYER.
            enemy.TargetPlayer(player)
                        
            # TRY TO SHOOT AT THE PLAYER.
            laser = enemy.TryShooting(time_since_last_update_in_seconds, player, self.Map)
            if laser:
                self.Map.Lasers.append(laser)

            # MOVE IF NON-STATIONARY.
            enemy_is_stationary = isinstance(enemy, Turret)
            if enemy_is_stationary:
                continue
            
            # CHECK IF THE ENEMY IS ALREADY CLOSE ENOUGH TO THE PLAYER.
            enemy_position = self.Map.GetGridPosition(enemy.Coordinates.center)
            enemy_position_vector = Vector2(enemy_position[0], enemy_position[1])
            distance_to_player = self.Pathing.GetDirectDistanceBetweenGridPositions(player_position_vector, enemy_position_vector)
            MINIMUM_DISTANCE = 3.5
            too_close_to_player = (distance_to_player < MINIMUM_DISTANCE)
            DESIRED_DISTANCE = 4.5
            within_desired_distance_of_player = (distance_to_player < DESIRED_DISTANCE)
            if too_close_to_player:
                # BACK AWAY FROM THE PLAYER.
                directions_to_move = LevelHandler.GetDirectionTowardPosition(player_position_vector, enemy_position_vector)
                pass
            elif within_desired_distance_of_player:
                # DON'T MOVE.
                continue
            else:
                # MOVE TOWARD THE PLAYER.
                # Get the shortest path to the player from the enemy.
                path_to_player = self.Pathing.GetPath(enemy_position_vector, player_position_vector)
                if path_to_player is None:
                    # This enemy cannot currently reach the player.
                    continue

                # Get the cardinal direction in which the enemy should move in order to reach
                # the player (or directions, if the true direction is diagonal).
                next_grid_position_in_path_to_player = next(islice(path_to_player, 1, None), None)
                next_grid_position_center_x = (next_grid_position_in_path_to_player.X + 0.5) * GameObject.WidthPixels
                next_grid_position_center_y = (next_grid_position_in_path_to_player.Y + 0.5) * GameObject.HeightPixels
                directions_to_move = LevelHandler.GetDirectionTowardPosition(
                    Vector2(enemy.Coordinates.centerx, enemy.Coordinates.centery),
                    Vector2(next_grid_position_center_x, next_grid_position_center_y))

            # MOVE.
            # If the true direction is diagonal, one of the directions to move may be blocked
            # by an obstacle, but trying to move in the other direction should succeed.
            for direction in directions_to_move:
                if direction == MoveDirection.Up:
                    enemy.MoveUp(self.Map)
                elif direction == MoveDirection.Down:
                    enemy.MoveDown(self.Map)
                elif direction == MoveDirection.Left:
                    enemy.MoveLeft(self.Map)
                elif direction == MoveDirection.Right:
                    enemy.MoveRight(self.Map)

    ## Gets the directions (up, down, left, or right) from one position to another.
    ## \param[in]  origin_position - The first position as a Vector2 of column and row index.
    ## \param[in]  target_position - The target position as a Vector2 of column and row index.
    ## \returns The direction (or directions if relationship is diagonal) from origin to target,
    ##      or an empty list if origin and target are the same position.
    ## \author  Tom Rogan
    ## \date    09/01/2018
    @staticmethod
    def GetDirectionTowardPosition(origin_position, target_position):
        directions = []
        if target_position is None:
            return directions
        if origin_position.Y > target_position.Y:
            directions.append(MoveDirection.Up)
        if origin_position.Y < target_position.Y:
            directions.append(MoveDirection.Down)
        if origin_position.X > target_position.X:
            directions.append(MoveDirection.Left)
        if origin_position.X < target_position.X:
            directions.append(MoveDirection.Right)
        return directions
