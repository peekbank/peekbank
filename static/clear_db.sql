SET FOREIGN_KEY_CHECKS=0;
delete from aoi_region_sets;
delete from aoi_timepoints;
delete from datasets;
delete from subjects;
delete from trials;
delete from administrations;
delete from xy_timepoints;
delete from stimuli;
ALTER TABLE aoi_region_sets AUTO_INCREMENT = 1;
ALTER TABLE aoi_timepoints AUTO_INCREMENT = 1;
ALTER TABLE datasets AUTO_INCREMENT = 1;
ALTER TABLE subjects AUTO_INCREMENT = 1;
ALTER TABLE trials AUTO_INCREMENT = 1;
ALTER TABLE administrations AUTO_INCREMENT = 1;
ALTER TABLE xy_timepoints AUTO_INCREMENT = 1
ALTER TABLE stimuli AUTO_INCREMENT = 1
SET FOREIGN_KEY_CHECKS=1;
