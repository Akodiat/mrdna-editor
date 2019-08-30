## Usage: vmd -e load-mrsim.tcl [-args ./path/to/simulation]
##   this script is not intended to be sourced from a running VMD session

## Check arguments for directory, then change into that directory
if {[llength $argv] == 1} {
    set prefix $argv; list
} elseif {[llength $argv] != 0} {
    puts "ERROR: 'load-mrsim.tcl' was not called in the expected way"
    exit -1
} else {
    set prefix ./
}   

## Find files
set cmd {set psf_files [lsort [glob $prefix*psf]]}; list
if [catch $cmd] {
    set cmd {set psf_files [lsort [glob $prefix/*psf]]}; list
    if [catch $cmd] {
	puts "ERROR: 'load-mrsim.tcl' was called with prefix '$prefix', but was unable to find simulation files"
	exit -1
    }
}

## Find coordinate_files
set mol_ids {}
foreach psf $psf_files {
    puts $psf
    set groups [regexp -inline {^((.*/)*)([^/]*).psf} $psf]
    puts $groups
    set directory [lindex $groups 1]
    set prefix [lindex $groups end]
    if {$directory == ""} { set directory . }
    puts $directory
    puts $prefix

    set ID [mol new $psf]
    mol off $ID
    lappend mol_ids $ID

    set dcd $directory/output/$prefix.dcd
    set pdb $directory/$prefix.pdb
    mol addfile $pdb
    if [file exists $dcd] {
	animate delete all ;# get beta from pdb
	mol addfile $dcd waitfor all
    }

    ## Update representation
    set sel [atomselect top "name C1'"]
    if {[$sel num] == 0} {
	mol representation CPK 10 12
    } else {
	mol representation VDW	    
    }
    mol modrep 0 $ID
    $sel delete
}

mol on [lindex $mol_ids 0]
mol top [lindex $mol_ids 0]
