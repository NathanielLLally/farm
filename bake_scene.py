#  bake_scene
#    no frills do what is tedious in order to bake every mesh in a scene
#
#for every mesh that is not render hidden from the selected scene
#  *if the mesh has any node that is glass, it will be skipped
#  *process will check materials, if there is no nodes for a material, nodes will be created
#  if there is no selected image texture file source
#    one will be created at Tex_Size as object.name+'_bake.jpg' in dir relative to blend
#  if there is a single selected image texture in one and only one material
#    every other material will have that image texture node created
#  if multiple selected image textures with different file names are among the materials
#    a new image texture with the size of the largest one will be created for all materials
#
#
#  all images will be saved with a '_bake' appended to 
#
#
#
#

import bpy
import os
import re
import sys
import time
import traceback #format_exception
import logging

#  max of two tuples on # of pixels
def maxArea(a,b):
	areaA = a[0] * a[1]
	areaB = b[0] * b[1]
	if (areaB > areaA):
		return b
	else:
		return a

def timeElapsed(then, now):
	hours, rem = divmod(now-then, 3600)
	minutes, seconds = divmod(rem, 60)
	logging.info(" time taken: {:0>2}:{:0>2}:{:05.2f}".format(int(hours),int(minutes),seconds))
	return;

#  look for a single selected image texture
#  return that image or the max of default size of any other image texture
def checkMaterials(obj):
	existing_image=None
	max_size = (0,0)
	conflict = False
	for slot in obj.material_slots:
		mat = slot.material
		#  determine if image texture(s) already set up for this object
		nodes = list(mat.node_tree.nodes)
		selected_tex = 0
		tex_node = None
		# one and only one selected image texture with a FILE for source
		# same file for all materials
		for node in nodes:
			if node.bl_idname == 'ShaderNodeGroup':
				nodes.extend(list(node.node_tree.nodes))
			if node.bl_idname == 'ShaderNodeBsdfGlass':
#					if link.to_node and link.is_valid:
				raise TypeError('Glass Shader found within '+obj.name+ ": " +mat.name)
			if node.bl_idname == 'ShaderNodeTexImage' and node.image.source == 'FILE':
				max_size = maxArea(max_size, node.image.size)
				if node.select == True:
					tex_node = node
					selected_tex+=1

		if selected_tex == 1:
			if existing_image:
				if not existing_image.filepath_raw == tex_node.image.filepath_raw:
					conflict = True
					max_size = maxArea(existing_image.size, tex_node.image.size)
					logging.info("object " + obj.name + " has multiple materials with different images selected")
#					raise "invalid object"
			else:
				existing_image = tex_node.image
			continue
	if not conflict and existing_image:
		img = add_tex(obj, existing_image, existing_image.size)
	else:
		if max_size != (0,0):
			img = add_tex(obj, None, max_size)
		else:
			img = add_tex(obj, None, Tex_Size)
	return img

def add_tex(obj, existing_image, size):
	# was an image passed in to be used
	if existing_image:
		image=existing_image
	else:
	#  otherwise, just add an image texture to every material
	#  with a new image named by the material name in the same directory
		#make and save a new image
		image_name = obj.name + Out_Postfix
		image = bpy.data.images.new(image_name, width=size[0], height=size[1])
		image.filepath_raw = "//" + Out_Dir + '/' + image_name + Out_Ext
		image.file_format = 'JPEG'
		image.save()

	# if this material was not the one with the set up image
	for slot in obj.material_slots:
		mat = slot.material
		nodes = mat.node_tree.nodes
		nodelist= list(nodes)
		has_node = 0
		for node in nodelist:
			if node.bl_idname == 'ShaderNodeGroup':
				nodelist.extend(list(node.node_tree.nodes))
			if node.bl_idname == 'ShaderNodeTexImage' and node.select == True and node.image.source == 'FILE' and node.image.filepath_raw == image.filepath_raw:
				has_node = 1
		if has_node:
			continue

	#then add image to a new texture node
		logging.info(" adding image texture to obj: "+obj.name+" "+ " material:" + mat.name + " size: "+str(image.size[0])+ ","+str(image.size[1])+")")

		# add texture node 
		node_tex = nodes.new(type='ShaderNodeTexImage')
		node_tex.image = image
		node_tex.select = True
	return image

def process(scene):
	bakeThese = []

	for obj in scene.objects:
	#  determine if we should (or can) bake this object
		has_activeUV = False
		has_material = False
		has_nodes = True

		fail = False;

		if obj.type != 'MESH':
			logging.info(obj.name + ' type '+obj.type + ' not a mesh')
			continue
  # not if its a cycles light plane
		if obj.cycles_visibility.camera != True:
			logging.info("object "+obj.name+".cycles_visibility.camera False");
			fail = True
  # or an extraneous image user didn't delete
		if obj.hide_render == True:
			logging.info("object "+obj.name+" hidden from render");
			fail = True
		#no active UVMap
		for uvmap in obj.data.uv_textures:
			if uvmap.active_render:
				has_activeUV = True

		if not has_activeUV:
			fail = True
			logging.info("object "+obj.name+" has no active UV")

		#has a material with nodes
		for slot in obj.material_slots:
			mat = slot.material
			if mat:
				has_material = True
				if not mat.node_tree.nodes:
					logging.info("object "+obj.name+" material "+mat.name + " has no nodes")
					fail = True
					continue

		if not has_material:
				logging.info("object "+obj.name+" has no material")
				fail = True

		if fail:
			continue

		try:
#			logging.info("checking "+obj.name+ " materials")
			ret = checkMaterials(obj)
#		except TypeError:
#			logging.info("invalid object: ",obj.name," material ", e
		except :
			exc_type, exc_value, exc_traceback = sys.exc_info()
			lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
			logging.info(''.join('!! ' + line for line in lines))  # Log it or whatever here
			continue

		logging.info("object "+obj.name+ " will bake at ("+str(ret.size[0])+","+str(ret.size[1])+")")

		bakeThese.append(obj)
	return bakeThese;

def fix_nodes(objects):
	for obj in objects:
		logging.info("fixing nodes for : " +obj.name)

def bake(scene,objects):
	for obj in scene.objects:
		obj.select = False

	startBake = time.time()
	for obj in objects:
		scene.objects.active = obj
		obj.select = True
	
		logging.info("baking object " + obj.name)
		if not testrun:
			then = time.time()
			bpy.ops.object.bake(type='COMBINED')
			timeElapsed(then,time.time())

		obj.select = False

		# save all baked images
		for image in bpy.data.images:
			if image.is_dirty:
				if image.source == 'FILE':
        # foo.png -> foo_bake.png
					filepath, filepath_ext = os.path.splitext(image.filepath_raw)
					image.filepath_raw = '//'+Out_Dir+'/'+os.path.basename(filepath)
				else:
					filepath_ext = image.file_format.lower()
					image.filepath_raw = '//'+Out_Dir+'/unknown'
					image.filepath_ext = '.jpg'

				if not re.match('.*'+Out_Postfix+'$', image.filepath_raw):
					image.filepath_raw += Out_Postfix + Out_Ext
				if not testrun:
					image.save()

	logging.info("total time taken:")
	timeElapsed(then,time.time())

#  MAIN
#
#  globals
######################

logger = logging.getLogger()
#handler = logging.StreamHandler()
handler = logging.FileHandler(filename='bake_scene.log')
formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
#        '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
#logging.basicConfig(filename='bake_scene.log', level=logging.DEBUG)

#  default new texture size for baked image
Tex_Size = 512,512
Max_Size = 2048, 2048

Scene = bpy.context.scene

argv = sys.argv
argv = argv[argv.index("--") + 1:]  # get all args after "--"
logging.info("arguments:" + str(argv))

debug = False
testrun = False
for i,arg in enumerate(argv):
	if arg == 'debug':
		debug = True
	if arg == 'test':
		testrun = True
	if arg == 'seed':
		Scene.cycles.seed=int(argv.pop(i+1))
	if arg == 'samples':
		Scene.cycles.use_square_samples = False
		Scene.cycles.samples = int(argv.pop(i+1))

cwd=os.getcwd()
Out_Dir = './bake_scene'
Out_Postfix = "_bake_" + str('%02d' % Scene.cycles.seed)
Out_Ext = '.jpg'
if not os.path.exists(Out_Dir):
    os.makedirs(Out_Dir)

Scene.render.engine = 'CYCLES';
#if Scene.ats_settings.is_enabled:
#	Scene.ats_settings.is_enabled = False
if Scene.cycles.device == 'GPU':
	Scene.render.tile_x = 256
	Scene.render.tile_y = 256
elif Scene.cycles.device == 'CPU':
	Scene.render.tile_x = 16
	Scene.render.tile_y = 16

logging.info("Scene settings:")
logging.info("render.engine: "+Scene.render.engine)
logging.info("cycles.seed: "+str(Scene.cycles.seed))
logging.info("cycles.device: "+Scene.cycles.device)
logging.info("render.tile_x, tile_y: "+str(Scene.render.tile_x)+","+str(Scene.render.tile_y))
logging.info("cycles.samples: "+str(Scene.cycles.samples))
logging.info("cycles.use_square_samples"+ str(Scene.cycles.use_square_samples))

###############################
objects = process(Scene)
notBaking = set(Scene.objects).difference(set(objects))
logging.info("not baking the following invalid objects:")
logging.info("\n".join("\t"+o.name for o in notBaking))

if debug:
	bpy.ops.wm.save_as_mainfile(filepath="processed.blend")

if not testrun:
	bake(Scene,objects)
	fix_nodes(objects)
	bpy.ops.wm.save_as_mainfile(filepath="baked.blend")
