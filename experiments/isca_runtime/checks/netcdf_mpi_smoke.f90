program netcdf_mpi_smoke
  use mpi
  use netcdf
  implicit none

  integer :: ierr, rank, nprocs, ncid

  call MPI_Init(ierr)
  call MPI_Comm_rank(MPI_COMM_WORLD, rank, ierr)
  call MPI_Comm_size(MPI_COMM_WORLD, nprocs, ierr)

  if (rank == 0) then
    ierr = nf90_create("netcdf_mpi_smoke.nc", NF90_CLOBBER, ncid)
    if (ierr /= NF90_NOERR) then
      print *, "NETCDF_CREATE_FAILED:", trim(nf90_strerror(ierr))
      call MPI_Abort(MPI_COMM_WORLD, 2, ierr)
    end if
    ierr = nf90_close(ncid)
    if (ierr /= NF90_NOERR) then
      print *, "NETCDF_CLOSE_FAILED:", trim(nf90_strerror(ierr))
      call MPI_Abort(MPI_COMM_WORLD, 3, ierr)
    end if
  end if

  call MPI_Barrier(MPI_COMM_WORLD, ierr)
  print *, "MPI_NETCDF_OK rank", rank, "of", nprocs
  call MPI_Finalize(ierr)
end program netcdf_mpi_smoke
