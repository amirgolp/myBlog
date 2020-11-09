################
#
#
# Generate training data via OpenFOAM
#
################

import os, math, sys, random
import numpy as np
import utils 

# x_loc = []

# with open('x_loc.csv') as csv_file:
    # csv_reader = csv.reader(csv_file, delimiter=',')
    # line_count = 0
    # for row in csv_reader:
        # if line_count == 0:
            # line_count += 1
        # else:
            # x_loc.append(float(row[0]))

samples           = 1           # no. of datasets to produce
freestream_angle  = math.pi / 8.  # -angle ... angle
freestream_length = 10e-5           # len * (1. ... factor)
freestream_length_factor = 10.    # length factor

porous_database  = "./porousMedia/"
output_dir        = "./train/"

seed = random.randint(0, 2**32 - 1)
np.random.seed(seed)
print("Seed: {}".format(seed))
	
def genMesh(porousFile):

    os.system("./Allprep")
    if os.system("cp ../porousMedia/" + porousFile + " .") != 0:
        print("error during mesh creation!")
        return(-1)
    os.system("cp -r ../of.org/0 . > /dev/null")
    os.system("mv "+ porousFile + " MeshedSurface.obj  > /dev/null")
    os.system("extrude2DMesh -overwrite MeshedSurface  > /dev/null")
    
    if os.system("checkMesh > /dev/null") != 0:
        print("problem with mesh. Checkmesh failed!")
        return(-1)
    
    os.system("cp -r system/topoSetDict.inlet system/topoSetDict  > /dev/null")
    os.system("topoSet | tee log.topoSet > /dev/null")    
    with open("log.topoSet", 'r') as read_obj:
        # Read all lines in the file one by one
        for line in read_obj:
            # For each line, check if line contains the string
            if "faceSet filter1 now size 0" in line:
                print("inlet patch is not generated. Consider removing {}.".format(porousFile))
                os.system("rm -rf ../porousMedia/{}".format(porousFile))
                return (-1)
    
    os.system("cp -r system/createPatchDict.inlet system/createPatchDict  > /dev/null")
    os.system("createPatch -overwrite  > /dev/null")
    os.system("rm -rf constant/polyMesh/sets > /dev/null")
    os.system("cp -r system/topoSetDict.outlet system/topoSetDict  > /dev/null")
    os.system("topoSet | tee log.topoSet  > /dev/null")
    with open("log.topoSet", 'r') as read_obj:
        for line in read_obj:
            if "faceSet filter1 now size 0" in line:
                print("outlet patch is not generated. Consider removing {}.".format(porousFile))
                os.system("rm -rf ../porousMedia/{}".format(porousFile))
                return (-1)
    os.system("cp -r system/createPatchDict.outlet system/createPatchDict  > /dev/null")
    os.system("createPatch -overwrite  > /dev/null")
    os.system("rm -rf constant/polyMesh/sets  > /dev/null")
    os.system("transformPoints -scale \"(1e-4 1e-4 1e-4)\"  > /dev/null")   
    os.system("sed -i 's/wall/patch/g' constant/polyMesh/boundary")
    os.system("sed -i -z 's/patch/wall/' constant/polyMesh/boundary")
    os.system("sed -i 's/default/walls/g' constant/polyMesh/boundary")
    
    return(0)

def runSim(freestreamX, freestreamY):
    with open("U_template", "rt") as inFile:
        with open("0/U", "wt") as outFile:
            for line in inFile:
                line = line.replace("VEL_X", "{}".format(freestreamX))
                line = line.replace("VEL_Y", "{}".format(freestreamY))
                outFile.write(line)

    if os.system("simpleFoam > foam.log > /dev/null") != 0:
        print("simpleFoam failed to run!")
        return (-1)
    
    return (0)
		
def outputProcessing(basename, freestreamX, freestreamY, dataDir=output_dir, pfile='OpenFOAM/postProcessing/internalCloud/500/cloud_p.xy', ufile='OpenFOAM/postProcessing/internalCloud/500/cloud_U.xy', res=128, imageIndex=0): 
    # output layout channels:
    # [0] freestream field X + boundary
    # [1] freestream field Y + boundary
    # [2] binary mask for boundary
    # [3] pressure output
    # [4] velocity X output
    # [5] velocity Y output
    
    
    npOutput = np.zeros((6, res, res))

    arP = np.loadtxt(pfile)
    arU = np.loadtxt(ufile)
    
    curIndex = 0
    dx = 0.005/(res - 1)
    
    while curIndex < (arP.shape[0]-1):
        entryFound = False
        xf = arP[curIndex][0]
        xf = round(xf/dx, 3)
        xf = int(xf)

        yf = arP[curIndex][1]
        yf = round(yf/dx, 3)
        yf = int(yf)
        
        for y in range(res):
            for x in range(res):
                
                if abs(x - xf)<1e-4 and abs(y - yf)<1e-4:
                    #fill pressure
                    npOutput[3][x][y] = arP[curIndex][3]
                    # fill input as well
                    npOutput[0][x][y] = freestreamX
                    npOutput[1][x][y] = freestreamY
                    # fill mask
                    npOutput[2][x][y] = 1.0
                    #fill velocities
                    npOutput[4][x][y] = arU[curIndex][3]
                    npOutput[5][x][y] = arU[curIndex][4]
                    #reading next line in the file
                    curIndex += 1
                    entryFound = True
                    continue
                # else:
                #     npOutput[3][x][y] = 0
                #     # fill mask
                #     npOutput[2][x][y] = 0.0
            if entryFound:
                continue


    utils.saveAsImage('data_pictures/pressure_%04d.png'%(imageIndex), npOutput[3])
    utils.saveAsImage('data_pictures/velX_%04d.png'  %(imageIndex), npOutput[4])
    utils.saveAsImage('data_pictures/velY_%04d.png'  %(imageIndex), npOutput[5])
    utils.saveAsImage('data_pictures/inputX_%04d.png'%(imageIndex), npOutput[0])
    utils.saveAsImage('data_pictures/inputY_%04d.png'%(imageIndex), npOutput[1])

    #fileName = dataDir + str(uuid.uuid4()) # randomized name
    fileName = dataDir + "%s_%d_%d" % (basename, int(freestreamX*10000), int(freestreamY*10000) )
    print("\tsaving in " + fileName + ".npz")
    np.savez_compressed(fileName, a=npOutput)
    
    return (0)


files = os.listdir(porous_database)
files.sort()
if len(files)==0:
	print("error - no samples found in %s" % porous_database)
	exit(1)

utils.makeDirs( ["./data_pictures", "./train", "./OpenFOAM/constant/polyMesh/sets", "./OpenFOAM/constant/polyMesh"] )


# main
for n in range(samples):
    print("Run {}:".format(n))

    fileNumber = np.random.randint(0, len(files))
    basename = os.path.splitext( os.path.basename(files[fileNumber]) )[0]
    print("\tusing {}".format(files[fileNumber]))

    length = freestream_length * np.random.uniform(1.,freestream_length_factor) 
    angle  = np.random.uniform(-freestream_angle, freestream_angle) 
    fsX =  math.cos(angle) * length
    fsY = -math.sin(angle) * length

    print("\tUsing len %5.3f angle %+5.3f " %( length,angle )  )
    print("\tResulting freestream vel x,y: {},{}".format(fsX,fsY))

    os.chdir("./OpenFOAM/")
    if genMesh(files[fileNumber]) != 0:
        print("\tmesh generation failed, aborting");
        os.chdir("..")
        continue
    
    if runSim(fsX, fsY) == 0:
        os.chdir("..")
        os.system("echo $PWD")
        os.system("rm -rf cs*.csv combined_csv.csv")
        outputProcessing(basename, fsX, fsY, imageIndex=n)
    else:
        print("\tsimpleFoam failed to run, aborting");
        continue
    print("\tdone")
