cmake_minimum_required(VERSION 3.14)
project(ChipletPart VERSION 1.0)

# Specify the C++ standard.
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Default build type is Release.
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING 
      "Choose the type of build, options are: Debug, Release, RelWithDebInfo, MinSizeRel." FORCE)
endif()

# Set output directories.
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# ---------------------------------------------------------------------------
# Global compiler flags for better portability on your machine.
# ---------------------------------------------------------------------------
# Use a conservative optimization level and target native architecture.
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -O2 -march=native")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -march=native")

# ---------------------------------------------------------------------------
# Boost
# ---------------------------------------------------------------------------
find_package(Boost 1.71.0 REQUIRED)
if(Boost_FOUND)
  message(STATUS "Boost found: enabling high-precision math functions")
  include_directories(${Boost_INCLUDE_DIRS})
else()
  message(FATAL_ERROR "Boost library not found")
endif()

# ---------------------------------------------------------------------------
# OpenMP
# ---------------------------------------------------------------------------
option(ENABLE_OPENMP "Enable OpenMP for parallel processing" ON)
if(ENABLE_OPENMP)
  message(STATUS "OpenMP support is enabled")
  find_package(OpenMP)
  if(OpenMP_CXX_FOUND)
    message(STATUS "OpenMP found: enabling parallel processing")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${OpenMP_CXX_FLAGS}")
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${OpenMP_C_FLAGS}")
    add_definitions(-DHAVE_OPENMP=1)
  else()
    message(STATUS "OpenMP not found: parallel processing will be disabled")
    add_definitions(-DHAVE_OPENMP=0)
  endif()
else()
  message(STATUS "OpenMP support is disabled by user configuration")
  add_definitions(-DHAVE_OPENMP=0)
endif()

# ---------------------------------------------------------------------------
# METIS and GKlib (local installation)
# ---------------------------------------------------------------------------
# Set the METIS/GKlib root directories relative to this checkout.
set(METIS_ROOT "${PROJECT_SOURCE_DIR}/METIS")
set(GKLIB_ROOT "${PROJECT_SOURCE_DIR}/GKlib")

# Include GKlib headers so that types like idx_t and real_t are defined.
include_directories(${GKLIB_ROOT}/include)

if(EXISTS "${METIS_ROOT}/include/metis.h")
    add_definitions(-DIDXTYPEWIDTH=64)
    add_definitions(-DREALTYPEWIDTH=64)
    message(STATUS "Using local METIS from ${METIS_ROOT}")
    include_directories(${METIS_ROOT}/include)
    
    add_subdirectory(${GKLIB_ROOT} ${CMAKE_BINARY_DIR}/GKlib-build EXCLUDE_FROM_ALL)

    file(GLOB METIS_SOURCES "${METIS_ROOT}/libmetis/*.c")
    if(METIS_SOURCES)
        add_library(metis STATIC ${METIS_SOURCES})
        target_include_directories(metis PUBLIC
            ${METIS_ROOT}/include
            ${METIS_ROOT}/libmetis
            ${GKLIB_ROOT}/include)
        target_compile_definitions(metis PUBLIC IDXTYPEWIDTH=64 REALTYPEWIDTH=64)
        target_link_libraries(metis PUBLIC GKlib)
        message(STATUS "Built local METIS static library from ${METIS_ROOT}")
        set(HAVE_METIS TRUE)
    else()
        message(FATAL_ERROR "No METIS source files found in ${METIS_ROOT}/libmetis")
    endif()
else()
    message(FATAL_ERROR "Local METIS not found in ${METIS_ROOT}/include")
endif()

# ---------------------------------------------------------------------------
# Eigen
# ---------------------------------------------------------------------------
find_package(Eigen3 REQUIRED)
if(Eigen3_FOUND)    
    message(STATUS "Found installed Eigen library at ${Eigen3_INCLUDE_DIRS}")
    include_directories(${Eigen3_INCLUDE_DIRS})
else()
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/include/eigen3/Eigen/Dense")
        message(STATUS "Found local Eigen library in include directory")
        include_directories("${CMAKE_CURRENT_SOURCE_DIR}/include/eigen3")
    else()
        message(STATUS "Eigen not found - downloading from GitLab")
        include(FetchContent)
        FetchContent_Declare(
            eigen
            GIT_REPOSITORY https://gitlab.com/libeigen/eigen.git
            GIT_TAG 3.4.0
            GIT_SHALLOW ON
        )
        FetchContent_Populate(eigen)
        file(MAKE_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/include/eigen3")
        file(COPY "${eigen_SOURCE_DIR}/Eigen" DESTINATION "${CMAKE_CURRENT_SOURCE_DIR}/include/eigen3")
        file(COPY "${eigen_SOURCE_DIR}/unsupported" DESTINATION "${CMAKE_CURRENT_SOURCE_DIR}/include/eigen3")
        message(STATUS "Copied Eigen headers to ${CMAKE_CURRENT_SOURCE_DIR}/include/eigen3")
        include_directories("${CMAKE_CURRENT_SOURCE_DIR}/include/eigen3")
    endif()
endif()

# ---------------------------------------------------------------------------
# Pugixml
# ---------------------------------------------------------------------------
add_library(pugixml STATIC ${PROJECT_SOURCE_DIR}/src/pugixml.cpp)
target_include_directories(pugixml PUBLIC ${PROJECT_SOURCE_DIR}/src)
include_directories(${PROJECT_SOURCE_DIR})

# ---------------------------------------------------------------------------
# Global include directories
# ---------------------------------------------------------------------------
include_directories(${PROJECT_SOURCE_DIR})
include_directories(${PROJECT_SOURCE_DIR}/src)
include_directories(${PROJECT_SOURCE_DIR}/include)
include_directories(${PROJECT_SOURCE_DIR}/cost_model)
include_directories(${PROJECT_SOURCE_DIR}/cost_model/include)

# ---------------------------------------------------------------------------
# Options for building components
# ---------------------------------------------------------------------------
option(BUILD_COST_MODEL "Build the cost model component" ON)
option(BUILD_MAIN_APP "Build the main ChipletPart application" ON)
option(BUILD_THERMAL_TESTS "Build thermal integration smoke tests" ON)

if(BUILD_COST_MODEL)
    add_subdirectory(cost_model)
endif()

if(BUILD_THERMAL_TESTS AND BUILD_COST_MODEL)
    add_executable(thermal_mvp_test
        src/test/test_thermal_mvp.cpp
        src/ThermalAwareEvaluator.cpp
        src/ThermalAwareEvaluator.h
        src/ThermalConfig.h)

    target_link_libraries(thermal_mvp_test PRIVATE cost_model pugixml ${Boost_LIBRARIES} Eigen3::Eigen)

    if(OpenMP_CXX_FOUND)
        target_link_libraries(thermal_mvp_test PRIVATE ${OpenMP_CXX_LIBRARIES})
    endif()

    enable_testing()
    add_test(NAME thermal_mvp_test
             COMMAND thermal_mvp_test ${PROJECT_SOURCE_DIR}/test_data/48_1_14_4_1600_1600)

    add_executable(thermal_collect_cli
        src/test/thermal_collect_cli.cpp
        src/ThermalAwareEvaluator.cpp
        src/ThermalAwareEvaluator.h
        src/ThermalConfig.h)

    target_link_libraries(thermal_collect_cli PRIVATE cost_model pugixml ${Boost_LIBRARIES} Eigen3::Eigen)

    if(OpenMP_CXX_FOUND)
        target_link_libraries(thermal_collect_cli PRIVATE ${OpenMP_CXX_LIBRARIES})
    endif()
elseif(BUILD_THERMAL_TESTS)
    message(WARNING "BUILD_THERMAL_TESTS requires BUILD_COST_MODEL=ON; skipping thermal tests")
endif()

if(BUILD_MAIN_APP)
    add_executable(chipletPart 
        src/Main.cpp 
        src/Hypergraph.cpp 
        src/Utilities.cpp 
        src/ChipletPart.cpp
        src/FMRefiner.cpp 
        src/PriorityQueue.cpp 
        src/GeneticTechPartitioner.cpp
        src/ThermalAwareEvaluator.cpp
        src/floorplan.cpp
        src/KLRefiner.cpp
        src/KLRefiner.h
        src/Console.h
        src/ChipletPart.h
        src/FMRefiner.h
        src/PriorityQueue.h
        src/Utilities.h
        src/Hypergraph.h
        src/floorplan.h
        src/GeneticTechPartitioner.h
        src/ThermalAwareEvaluator.h
        src/ThermalConfig.h
        src/CanonicalGA.cpp
        src/CanonicalGA.h
        src/KLRefiner.cpp
        src/KLRefiner.h
        src/omp_utils.h)
        
    target_link_libraries(chipletPart PRIVATE cost_model pugixml ${Boost_LIBRARIES} Eigen3::Eigen)
    
    # Link METIS and GKlib if available and not disabled (on non-Apple platforms)
    if(HAVE_METIS AND (NOT APPLE))
        target_link_libraries(chipletPart PRIVATE metis GKlib)
    endif()
    
    # Link OpenMP if found.
    if(OpenMP_CXX_FOUND)
        target_link_libraries(chipletPart PRIVATE ${OpenMP_CXX_LIBRARIES})
    endif()
endif()

# ---------------------------------------------------------------------------
# Compiler flags for different build types
# ---------------------------------------------------------------------------
set(CMAKE_CXX_FLAGS_DEBUG "-g")
set(CMAKE_CXX_FLAGS_RELEASE "-O3")
